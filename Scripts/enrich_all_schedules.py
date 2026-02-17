#!/usr/bin/env python3
"""
Match Enrichment Pipeline: Process ALL schedules to extract missing data
Author: LeoBook Team
Date: 2026-02-13

Purpose:
  - Visit ALL match URLs in schedules.csv (22k+)
  - Extract team IDs, league IDs, final scores, crests, URLs
  - Upsert teams.csv and region_league.csv with ALL columns
  - (--standings) Click Standings tab, extract league table, save to standings.csv
  - (--backfill-predictions) Fix region_league/crest URLs in predictions.csv
  - Fix "Unknown" or "N/A" entries
  - Smart date/time parsing for merged datetime strings
  - ALL selectors loaded dynamically from knowledge.json

Usage:
  python Scripts/enrich_all_schedules.py [--limit N] [--dry-run] [--standings] [--backfill-predictions]
"""

import asyncio
import csv
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import pandas as pd
import re

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from playwright.async_api import Playwright, async_playwright, Browser
from Data.Access.sync_manager import SyncManager, run_full_sync
from Data.Access.db_helpers import (
    SCHEDULES_CSV, TEAMS_CSV, REGION_LEAGUE_CSV, STANDINGS_CSV, PREDICTIONS_CSV,
    save_team_entry, save_region_league_entry, save_schedule_entry,
    save_standings, backfill_prediction_entry
)
from Data.Access.outcome_reviewer import smart_parse_datetime
from Core.Browser.Extractors.standings_extractor import extract_standings_data, activate_standings_tab
from Core.Browser.Extractors.league_page_extractor import extract_league_match_urls
from Modules.Flashscore.fs_utils import retry_extraction
from Core.Utils.constants import NAVIGATION_TIMEOUT, WAIT_FOR_LOAD_STATE_TIMEOUT

# Configuration
CONCURRENCY = int(os.getenv('ENRICH_CONCURRENCY', 5))  # Default 5 for stability
BATCH_SIZE = int(os.getenv('ENRICH_BATCH_SIZE', 10))   # Report progress more frequently
KNOWLEDGE_PATH = Path(__file__).parent.parent / "Config" / "knowledge.json"
HISTORICAL_GAP_LIMIT = 500  # Prevent Priority 3 bloat

# Selective dynamic selectors will still be used but Core/ extracts will handle standings


def load_selectors() -> Dict[str, str]:
    """Load fs_match_page selectors from knowledge.json."""
    with open(KNOWLEDGE_PATH, 'r', encoding='utf-8') as f:
        knowledge = json.load(f)
    selectors = knowledge.get("fs_match_page", {})
    if not selectors:
        raise RuntimeError("fs_match_page selectors not found in knowledge.json")
    print(f"[INFO] Loaded {len(selectors)} selectors from knowledge.json (fs_match_page)")
    return selectors


from Core.Intelligence.selector_manager import SelectorManager

async def _raw_safe_attr(page, selector: str, attr: str) -> Optional[str]:
    """Raw attribute extraction for smart wrapper."""
    try:
        el = await page.query_selector(selector)
        if el:
            val = await el.get_attribute(attr)
            return val.strip() if val else None
    except:
        pass
    return None


async def _raw_safe_text(page, selector: str) -> Optional[str]:
    """Raw text extraction for smart wrapper."""
    try:
        el = await page.query_selector(selector)
        if el:
            val = await el.inner_text()
            return val.strip() if val else None
    except:
        pass
    return None


async def _smart_attr(page, context: str, key: str, attr: str) -> Optional[str]:
    """Safe extraction using direct selector lookup with hardening."""
    try:
        selector = SelectorManager.get_selector(context, key)
        if selector:
            # Hardening: Wait for selector if it might be dynamic
            try:
                await page.wait_for_selector(selector, timeout=2000)
            except: pass
            return await _raw_safe_attr(page, selector, attr)
    except:
        pass
    return None

async def _smart_text(page, context: str, key: str) -> Optional[str]:
    """Safe extraction using direct selector lookup with hardening."""
    try:
        selector = SelectorManager.get_selector(context, key)
        if selector:
            # Hardening: Wait for selector if it might be dynamic
            try:
                await page.wait_for_selector(selector, timeout=2000)
            except: pass
            
            text = await _raw_safe_text(page, selector)
            if text and text.lower() == "loading...":
                await asyncio.sleep(2)
                text = await _raw_safe_text(page, selector)
            return text
    except:
        pass
    return None


async def _smart_text(page, context: str, key: str) -> Optional[str]:
    """Safe text extraction using direct selector lookup."""
    try:
        selector = SelectorManager.get_selector(context, key)
        if selector:
            return await _raw_safe_text(page, selector)
    except:
        pass
    return None


def _id_from_href(href: str) -> Optional[str]:
    """Extract entity ID from a flashscore URL like /team/name/ABC123/."""
    if not href:
        return None
    parts = href.strip('/').split('/')
    return parts[-1] if len(parts) >= 2 else None


def _standardize_url(url: str) -> str:
    """Ensure flashscore URLs are absolute."""
    if not url:
        return ''
    if url.startswith('//'):
        return 'https:' + url
    if url.startswith('/'):
        return 'https://www.flashscore.com' + url
    return url


def strip_league_stage(league_name: str):
    """Strips ' - Round X' etc. and returns (clean_league, stage)."""
    if not league_name: return "", ""
    # Common patterns: ' - Round 25', ' - Group A', ' - Play Offs', ' - Qualification'
    match = re.search(r" - (Round \d+|Group [A-Z]|Play Offs|Qualification|Relegation Group|Championship Group|Finals?)$", league_name, re.IGNORECASE)
    if match:
        stage = match.group(1)
        base_league = league_name[:match.start()].strip()
        return base_league, stage
    return league_name, ""


async def extract_match_enrichment(page, match_url: str, sel: Dict[str, str],
                                    extract_standings: bool = False,
                                    needs: List[str] = None) -> Optional[Dict]:
    """
    Extract team IDs, crests, URLs, league info, score, datetime, and optionally standings.
    Targeted extraction based on 'needs'.
    """
    if not needs: needs = ['ids', 'date', 'time', 'region_league', 'league_id', 'scores']
    
    try:
        # Use retry for navigation
        async def _navigate():
            await page.goto(match_url, wait_until='domcontentloaded', timeout=NAVIGATION_TIMEOUT)
            await asyncio.sleep(1.0)
        
        await retry_extraction(_navigate)

        enriched = {}

        # --- HOME TEAM (IDs) ---
        if 'ids' in needs or 'league_id' in needs:
            home_href = await _smart_attr(page, "fs_match_page", "home_name", "href")
            if home_href:
                enriched['home_team_id'] = _id_from_href(home_href)
                enriched['home_team_url'] = _standardize_url(home_href)
            home_name = await _smart_text(page, "fs_match_page", "home_name")
            if home_name:
                enriched['home_team_name'] = home_name
            home_crest_src = await _smart_attr(page, "fs_match_page", "home_crest", "src")
            if home_crest_src:
                enriched['home_team_crest'] = _standardize_url(home_crest_src)

        # --- AWAY TEAM (IDs) ---
        if 'ids' in needs or 'league_id' in needs:
            away_href = await _smart_attr(page, "fs_match_page", "away_name", "href")
            if away_href:
                enriched['away_team_id'] = _id_from_href(away_href)
                enriched['away_team_url'] = _standardize_url(away_href)
            away_name = await _smart_text(page, "fs_match_page", "away_name")
            if away_name:
                enriched['away_team_name'] = away_name
            away_crest_src = await _smart_attr(page, "fs_match_page", "away_crest", "src")
            if away_crest_src:
                enriched['away_team_crest'] = _standardize_url(away_crest_src)

        # --- REGION + LEAGUE ---
        if 'region_league' in needs or 'league_id' in needs:
            region_name = await _smart_text(page, "fs_match_page", "region_name")
            if region_name:
                enriched['region'] = region_name

            league_name_text = await _smart_text(page, "fs_match_page", "league_url")
            if league_name_text:
                enriched['league'] = league_name_text

            if region_name and league_name_text:
                clean_league, stage = strip_league_stage(league_name_text)
                enriched['region_league'] = f"{region_name.upper()} - {clean_league}"
                enriched['league_stage'] = stage

            league_url_href = await _smart_attr(page, "fs_match_page", "league_url", "href")
            if league_url_href:
                enriched['league_url'] = _standardize_url(league_url_href)
                enriched['rl_id'] = _id_from_href(league_url_href)
                enriched['league_id'] = enriched['rl_id']

        # --- FINAL SCORE ---
        if 'scores' in needs:
            home_score = await _smart_text(page, "fs_match_page", "final_score_home")
            away_score = await _smart_text(page, "fs_match_page", "final_score_away")
            if home_score:
                enriched['home_score'] = home_score
            if away_score:
                enriched['away_score'] = away_score

        # --- MATCH DATETIME ---
        if 'date' in needs or 'time' in needs:
            try:
                dt_text = await _smart_text(page, "fs_match_page", "match_time")
                if dt_text:
                    date_part, time_part = smart_parse_datetime(dt_text)
                    if 'date' in needs and date_part:
                        enriched['date'] = date_part
                    if 'time' in needs and time_part:
                        enriched['match_time'] = time_part
            except:
                pass

        # --- LEAGUE_ID DEEP SCRAPE ---
        if 'league_id' in needs:
            # 3. League URL (Deep Scrape)
            league_url = await _smart_attr(page, "fs_match_page", "league_url", "href")
            if league_url:
                enriched['league_url'] = _standardize_url(league_url)
                # Parse ID from URL
                enriched['league_id'] = _id_from_href(league_url)
                enriched['rl_id'] = enriched['league_id']
                
                # Visit results page to get metadata
                try:
                    from Core.Browser.Extractors.league_page_extractor import extract_league_metadata
                    l_results_url = enriched.get('league_url')
                    if not l_results_url.endswith('/results/'): l_results_url = l_results_url.rstrip('/') + '/results/'
                    await page.goto(l_results_url, wait_until='domcontentloaded')
                    await asyncio.sleep(2)
                    
                    league_meta = await extract_league_metadata(page)
                    if league_meta:
                        enriched.update(league_meta)
                except: pass
            else:
                print(f"      [ALERT] No league URL found for {match_url}. Flagging for manual review.")
                enriched['match_status'] = 'manual_review_needed'

        # --- STANDINGS ---
        if extract_standings:
            try:
                from Core.Browser.Extractors.standings_extractor import activate_standings_tab, extract_standings_data
                tab_active = await activate_standings_tab(page)
                if tab_active:
                    standings_result = await retry_extraction(extract_standings_data, page)
                    if standings_result:
                        enriched['_standings_data'] = standings_result
            except: pass

        return enriched if enriched else None

    except Exception as e:
        print(f"      [ERROR] Failed to enrich {match_url}: {e}")
        return None


async def process_match_task_isolated(browser: Browser, match: Dict, sel: Dict[str, str], extract_standings: bool) -> Dict:
    """Worker to enrich a single match within its own context with failure diagnostics."""
    fixture_id = match.get('fixture_id', 'unknown')
    try:
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            ignore_https_errors=True
        )
        try:
            page = await context.new_page()
            needs = match.get('_enrich_needs', [])
            enriched = await extract_match_enrichment(page, match['match_link'], sel, extract_standings, needs)
            if enriched:
                match.update(enriched)
            else:
                # AIGO Fallback: Capture diagnostics on extraction failure
                log_dir = Path("Data/Logs/EnrichmentFailures") / fixture_id
                log_dir.mkdir(parents=True, exist_ok=True)
                
                screenshot_path = log_dir / "failure.png"
                html_path = log_dir / "source.html"
                
                await page.screenshot(path=str(screenshot_path))
                with open(html_path, "w", encoding='utf-8') as f:
                    f.write(await page.content())
                
                print(f"      [AIGO Fallback] Extraction failed for {fixture_id}. Diagnostics saved to {log_dir}")
                
        except Exception as e:
            # print(f"      [ISOLATION INFO] Failed to enrich {match.get('fixture_id')}: {str(e)[:100]}")
            pass
        finally:
            await context.close()
    except Exception as e:
        print(f"      [ISOLATION CRITICAL] Context creation failed for {fixture_id}: {e}")
    
    return match


async def enrich_batch(playwright: Playwright, matches: List[Dict], batch_num: int,
                       sel: Dict[str, str], extract_standings: bool = False,
                       concurrency: int = 5) -> List[Dict]:
    """Process a batch of matches with isolated contexts and throttled concurrency."""
    browser = await playwright.chromium.launch(
        headless=True,
        args=['--disable-gpu', '--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
    )
    
    semaphore = asyncio.Semaphore(concurrency)

    async def worker(match):
        async with semaphore:
            # Enhanced Jitter: random delay between 0.5 and 2.5 seconds
            import random
            jitter = 0.5 + random.random() * 2.0
            await asyncio.sleep(jitter)
            return await process_match_task_isolated(browser, match, sel, extract_standings)

    # Gather results for all matches in the batch
    results = await asyncio.gather(*(worker(m) for m in matches))
    
    await browser.close()
    return list(results)


def analyze_metadata_gaps(df: pd.DataFrame) -> pd.DataFrame:
    """
    Scans for gaps in schedules metadata:
    - Missing home_team_id / away_team_id
    - Unknown or empty region_league
    - Malformed or merged datetime strings
    """
    dt_pattern = r"^\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}$"
    
    # 1. Check ID gaps
    id_gap = (df['home_team_id'] == '') | (df['away_team_id'] == '')
    
    # 2. Check Region/League gaps
    rl_gap = (df['region_league'].str.contains('Unknown', case=False)) | (df['region_league'] == '')
    
    # 3. Check Datetime gaps (merged strings)
    # If match_time is like "14.02.2026 20:30", it needs splitting/fixing
    dt_malformed = ~df['match_time'].str.match(dt_pattern) & (df['match_time'] != '') & (df['match_time'].str.len() > 5)
    
    gaps_df = df[id_gap | rl_gap | dt_malformed]
    return gaps_df


async def resolve_metadata_gaps(df: pd.DataFrame, sync_manager: SyncManager) -> pd.DataFrame:
    """
    Attempts to resolve missing metadata by merging with the latest data from Supabase.
    """
    print(f"  [METADATA] Attempting to resolve gaps via Supabase merge...")
    
    # Fetch all schedules from Supabase (the source of truth)
    try:
        remote_df = sync_manager.supabase.table('schedules').select('*').execute()
        if not remote_df.data:
            return df
        
        df_remote = pd.DataFrame(remote_df.data).fillna('')
        if df_remote.empty:
            return df

        # We merge back into local df based on fixture_id
        # We only want to fill gaps, so we use combine_first or update
        df.set_index('fixture_id', inplace=True)
        df_remote.set_index('fixture_id', inplace=True)
        
        # Standardize remote columns to match CSV headers
        # Supabase uses snake_case, but our table_config/sync_manager should handle alignment.
        # Actually, let's just use update for keys that are missing in local
        df.update(df_remote, overwrite=False) # Only fill missing values
        
        df.reset_index(inplace=True)
        print(f"  [SUCCESS] Metadata resolution complete.")
    except Exception as e:
        print(f"  [WARNING] Remote metadata resolution failed: {e}")
        
    return df



# ...

async def enrich_all_schedules(limit: Optional[int] = None, dry_run: bool = False,
                                extract_standings: bool = False,
                                backfill_predictions: bool = False,
                                league_page: bool = False):
    """
    Main enrichment pipeline.
    
    Args:
        limit: Process only first N matches (for testing)
        dry_run: If True, don't write to CSV files
        extract_standings: If True, also extract standings data
        backfill_predictions: If True, fix region_league/crests in predictions.csv
    """
    print("=" * 80)
    print("  MATCH ENRICHMENT PIPELINE")
    flags = []
    if extract_standings: flags.append("standings")
    if backfill_predictions: flags.append("backfill-predictions")
    print(f"  Mode: {' + '.join(flags) if flags else 'Standard'}")
    print(f"  Concurrency: {CONCURRENCY}")
    print(f"  Batch Size: {BATCH_SIZE}")
    print("=" * 80)
    print("  PROLOGUE PHASE 1: CLOUD HANDSHAKE & SYNC")
    print("  Goal: Establish data parity between local CSVs and Supabase.")
    print("=" * 80)

    # Initialize Sync Manager
    sync_manager = SyncManager()
    if not dry_run:
        print("[INFO] Initiating Bi-Directional Cloud Handshake...")
        await sync_manager.sync_on_startup()
        print("[SUCCESS] Cloud Handshake Complete. Local and Remote systems are in sync.")
    else:
        print("[DRY-RUN] Skipping Cloud Handshake.")

    # Load selectors
    if not KNOWLEDGE_PATH.exists():
        print(f"[ERROR] Knowledge file not found at {KNOWLEDGE_PATH}")
        return

    with open(KNOWLEDGE_PATH, 'r', encoding='utf-8') as f:
        knowledge = json.load(f)
        sel = knowledge.get('fs_match_page', {})
    
    print(f"[INFO] Loaded {len(sel)} selectors from knowledge.json (fs_match_page)")

    # --- PHASE 0: LEAGUE PAGE HARVESTING (Proactive) ---
    if league_page:
        print("\n" + "=" * 80)
        print("  PHASE 0: LEAGUE PAGE HARVESTING")
        print("  Goal: Proactively harvest all match URLs from active leagues.")
        print("=" * 80)
        
        if not os.path.exists(REGION_LEAGUE_CSV):
            print("[WARNING] region_league.csv not found. Skipping league harvesting.")
        else:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                leagues_df = pd.read_csv(REGION_LEAGUE_CSV, dtype=str).fillna('')
                # Filter for leagues that have a URL
                active_leagues = leagues_df[leagues_df['league_url'] != ''].to_dict('records')
                
                print(f"[INFO] Scanning {len(active_leagues)} leagues for new matches...")
                
                new_match_urls = set()
                for league in active_leagues:
                    l_url = league.get('league_url')
                    l_name = f"{league.get('region', '')}: {league.get('league', '')}"
                    print(f"   [League] Harvesting {l_name}...")
                    
                    found_urls = await extract_league_match_urls(page, l_url, mode="results")
                    for url in found_urls:
                        new_match_urls.add(url)
                
                await browser.close()
                
                if new_match_urls:
                    print(f"[SUCCESS] Harvested {len(new_match_urls)} total match URLs from league pages.")
                    # Load current schedules to avoid duplicates
                    df_current = pd.read_csv(SCHEDULES_CSV, dtype=str).fillna('')
                    existing_links = set(df_current['match_link'].tolist())
                    
                    added_count = 0
                    for m_url in new_match_urls:
                        if m_url not in existing_links:
                            # Add basic entry
                            new_entry = {
                                'fixture_id': m_url.split('/')[2] if '/match/' in m_url else 'Unknown',
                                'date': 'Pending',
                                'match_time': 'Pending',
                                'match_status': 'scheduled',
                                'match_link': m_url
                            }
                            # Use save_schedule_entry to handle defaults/headers
                            save_schedule_entry(new_entry)
                            added_count += 1
                    
                    print(f"[INFO] Added {added_count} new unique matches to schedules.csv")

    # --- PROLOGUE PAGE 2: MISSING METADATA ANALYSIS ---
    print("\n" + "=" * 80)
    print("  PROLOGUE PAGE 2: MISSING METADATA ANALYSIS")
    print("  Goal: Identify and resolve fixture gaps using Pandas & Cloud Merge.")
    print("=" * 80)

    # Load with Pandas for Analysis
    df_schedules = pd.read_csv(SCHEDULES_CSV, dtype=str).fillna('')
    
    # --- ROW CLEANUP: Remove invalid matches ---
    initial_count = len(df_schedules)
    df_schedules = df_schedules[~((df_schedules['fixture_id'] == '') & (df_schedules['match_link'] == ''))]
    removed_count = initial_count - len(df_schedules)
    if removed_count > 0:
        print(f"[CLEANUP] Removed {removed_count} rows with missing both fixture_id and match_link.")
        if not dry_run:
            df_schedules.to_csv(SCHEDULES_CSV, index=False, encoding='utf-8')

    gaps_found = analyze_metadata_gaps(df_schedules)
    print(f"[INFO] Initial scan found {len(gaps_found)} fixtures with structural metadata gaps.")
    
    if len(gaps_found) > 0 and not dry_run:
        df_schedules = await resolve_metadata_gaps(df_schedules, sync_manager)
        # Re-scan after resolution
        gaps_found = analyze_metadata_gaps(df_schedules)
        print(f"[INFO] Post-resolution gaps: {len(gaps_found)}")
        
        # Save resolved data
        df_schedules.to_csv(SCHEDULES_CSV, index=False, encoding='utf-8')

    # Convert to list of dicts for the enrichment loop
    all_matches = df_schedules.to_dict('records')
    
    # Filter matches based on Purpose-Driven Enrichment Needs
    to_enrich = []
    for m in all_matches:
        if not m.get('match_link'): continue
        
        needs = []
        if not m.get('home_team_id') or not m.get('away_team_id'): needs.append('ids')
        if m.get('date') in ('Pending', '', 'Unknown'): needs.append('date')
        if m.get('match_time') in ('Pending', '', 'Unknown'): needs.append('time')
        if m.get('region_league') in ('Unknown', 'N/A', ''): needs.append('region_league')
        if not m.get('league_id'): needs.append('league_id')
        if m.get('home_score') in ('N/A', '') or m.get('away_score') in ('N/A', ''):
             # Only if match is likely finished
             if m.get('match_status') == 'finished':
                 needs.append('scores')
        
        if needs:
            m['_enrich_needs'] = needs
            to_enrich.append(m)

    # --- ENRICHMENT PRIORITIZATION ---
    def get_priority(m):
        # Priority 1: Future matches (next 48h)
        # Priority 2: Recent past matches needing scores (last 24h)
        # Priority 3: Deep gaps
        try:
            d_str = m.get('date')
            t_str = m.get('match_time')
            if d_str == 'Pending' or not d_str: return 0 # High priority if date missing
            
            m_dt = datetime.strptime(f"{d_str} {t_str if t_str != 'Pending' else '00:00'}", "%d.%m.%Y %H:%M")
            now = datetime.now()
            
            if m_dt > now: return 1 # Future
            if (now - m_dt).days <= 1: return 2 # Recent Past
            return 3 # Deep Gap
        except:
            return 4 # Parsing error, low priority

    to_enrich.sort(key=get_priority)
    
    # --- Priority 3 Capping (Hardening) ---
    p3_count = 0
    final_to_enrich = []
    for m in to_enrich:
        p = get_priority(m)
        if p == 3:
            if p3_count < HISTORICAL_GAP_LIMIT:
                final_to_enrich.append(m)
                p3_count += 1
            else:
                continue # Skip excess historical gaps
        else:
            final_to_enrich.append(m)
    
    to_enrich = final_to_enrich
    print(f"  [PRIORITY] Sorted {len(to_enrich)} tasks. (Capped Priority 3 to {HISTORICAL_GAP_LIMIT})")

    # Calculate auto-scaling concurrency (2-5)
    calc_concurrency = max(2, min(5, len(to_enrich) // 20))
    print(f"  [AUTO-SCALE] Concurrency set to: {calc_concurrency}")

    if limit:
        to_enrich = to_enrich[:limit]

    print(f"[INFO] Total matches: {len(all_matches)}")
    print(f"[INFO] Matches to enrich: {len(to_enrich)}")

    if dry_run:
        print("[DRY-RUN] Simulating enrichment...")

    # Process in batches
    total_batches = (len(to_enrich) + BATCH_SIZE - 1) // BATCH_SIZE
    enriched_count = 0
    teams_added = set()
    leagues_added = set()
    standings_saved = 0
    predictions_backfilled = 0

    # Sync buffers
    sync_buffer_schedules = []
    sync_buffer_teams = []
    sync_buffer_leagues = []
    sync_buffer_standings = []

    async with async_playwright() as playwright:
        try:
            for batch_idx in range(0, len(to_enrich), BATCH_SIZE):
                batch = to_enrich[batch_idx:batch_idx + BATCH_SIZE]
                batch_num = (batch_idx // BATCH_SIZE) + 1

                print(f"\n[BATCH {batch_num}/{total_batches}] Processing {len(batch)} matches...")

                enriched_batch = await enrich_batch(playwright, batch, batch_num, sel, extract_standings, calc_concurrency)

                if not dry_run:
                    # Save enriched data
                    for match in enriched_batch:
                        # Update schedule
                        save_schedule_entry(match)
                        sync_buffer_schedules.append(match)

                        # Build rl_id for team -> league mapping
                        rl_id = match.get('rl_id', '')
                        region = match.get('region', '')
                        league = match.get('league', '')
                        if not rl_id and region and league:
                            rl_id = f"{region}_{league}".replace(' ', '_').replace('-', '_').upper()

                        # Upsert home team with ALL columns
                        if match.get('home_team_id'):
                            home_team_data = {
                                'team_id': match['home_team_id'],
                                'team_name': match.get('home_team_name', match.get('home_team', 'Unknown')),
                                'rl_ids': rl_id,
                                'team_crest': match.get('home_team_crest', ''),
                                'team_url': match.get('home_team_url', '')
                            }
                            save_team_entry(home_team_data)
                            teams_added.add(match['home_team_id'])
                            sync_buffer_teams.append(home_team_data)

                        # Upsert away team with ALL columns
                        if match.get('away_team_id'):
                            away_team_data = {
                                'team_id': match['away_team_id'],
                                'team_name': match.get('away_team_name', match.get('away_team', 'Unknown')),
                                'rl_ids': rl_id,
                                'team_crest': match.get('away_team_crest', ''),
                                'team_url': match.get('away_team_url', '')
                            }
                            save_team_entry(away_team_data)
                            teams_added.add(match['away_team_id'])
                            sync_buffer_teams.append(away_team_data)

                        # Upsert region_league with ALL columns
                        if rl_id:
                            league_data = {
                                'rl_id': rl_id,
                                'region': region,
                                'region_flag': match.get('region_flag', ''),
                                'region_url': match.get('region_url', ''),
                                'league': league,
                                'league_url': match.get('league_url', ''),
                                'league_crest': ''  # Not available on match page
                            }
                            save_region_league_entry(league_data)
                            leagues_added.add(rl_id)
                            sync_buffer_leagues.append(league_data)

                        # --- Save standings if extracted ---
                        standings_result = match.pop('_standings_data', None)
                        if standings_result:
                            s_data = standings_result.get('standings', [])
                            s_league = standings_result.get('region_league', 'Unknown')
                            s_url = standings_result.get('league_url', '')
                            if s_league == 'Unknown' and match.get('region_league'):
                                s_league = match['region_league']
                            if s_data and s_league != 'Unknown':
                                for row in s_data:
                                    row['url'] = s_url or match.get('league_url', '')
                                save_standings(s_data, s_league)
                                standings_saved += len(s_data)
                                sync_buffer_standings.extend(s_data)

                        # --- Backfill prediction if requested ---
                        if backfill_predictions and match.get('fixture_id'):
                            region_league = match.get('region_league', '')
                            updates = {}
                            if region_league and region_league != 'Unknown':
                                updates['region_league'] = region_league
                            if match.get('home_team_crest'):
                                updates['home_crest_url'] = match['home_team_crest']
                            if match.get('away_team_crest'):
                                updates['away_crest_url'] = match['away_team_crest']
                            if match.get('match_link'):
                                updates['match_link'] = match['match_link']
                            if updates:
                                was_updated = backfill_prediction_entry(match['fixture_id'], updates)
                                if was_updated:
                                    predictions_backfilled += 1
                                    # We should sync updated predictions too.
                                    # But backfill_prediction_entry doesn't return the full row.
                                    # This is complex. For now, rely on sync-on-startup or nightly sync.
                                    # asyncio.create_task(sync_manager.batch_upsert('predictions', [row]))

                        enriched_count += 1
                    
                    # --- PERIODIC SYNC (Every batch - fulfills "every 10 extractions") ---
                    if not dry_run:
                        print(f"   [SYNC] Upserting buffered data for batch {batch_num} to Supabase...")
                        if sync_buffer_schedules:
                            await sync_manager.batch_upsert('schedules', sync_buffer_schedules)
                            sync_buffer_schedules = []
                        if sync_buffer_teams:
                            await sync_manager.batch_upsert('teams', sync_buffer_teams)
                            sync_buffer_teams = []
                        if sync_buffer_leagues:
                            await sync_manager.batch_upsert('region_league', sync_buffer_leagues)
                            sync_buffer_leagues = []
                        if sync_buffer_standings:
                            await sync_manager.batch_upsert('standings', sync_buffer_standings)
                            sync_buffer_standings = []

                print(f"   [+] Enriched {len(enriched_batch)} matches")
                print(f"   [+] Teams: {len(teams_added)}, Leagues: {len(leagues_added)}")

        finally:
            # --- FINAL PROLOGUE SYNC (Chapter 0 Closure) ---
            if not dry_run:
                print(f"\n   [PROLOGUE] Initiating Final Global Sync...")
                # Ensure all buffers are flushed first (redundant but safe)
                if sync_buffer_schedules: await sync_manager.batch_upsert('schedules', sync_buffer_schedules)
                if sync_buffer_teams: await sync_manager.batch_upsert('teams', sync_buffer_teams)
                if sync_buffer_leagues: await sync_manager.batch_upsert('region_league', sync_buffer_leagues)
                if sync_buffer_standings: await sync_manager.batch_upsert('standings', sync_buffer_standings)
                
                # Perform global sync with verification and retries
                await run_full_sync()
                print(f"   [SUCCESS] Final global prologue sync complete.")

                # --- STEP 7: BUILD SEARCH DICTIONARY ---
                print(f"\n   [PROLOGUE] Rebuilding Search Dictionary...")
                try:
                    from Scripts.build_search_dict import main as build_search
                    build_search()
                    print(f"   [SUCCESS] Search dictionary rebuilt and synced.")
                except Exception as e:
                    print(f"   [Error] Failed to rebuild search dictionary: {e}")

    # Summary
    print("\n" + "=" * 80)
    print("  ENRICHMENT COMPLETE")
    print("=" * 80)
    print(f"  Total enriched:          {enriched_count}")
    print(f"  Teams updated:           {len(teams_added)}")
    print(f"  Leagues updated:         {len(leagues_added)}")
    if extract_standings:
        print(f"  Standings rows saved:    {standings_saved}")
    if backfill_predictions:
        print(f"  Predictions backfilled:  {predictions_backfilled}")

    if dry_run:
        print("\n[DRY-RUN] No files were modified")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Enrich all match schedules')
    parser.add_argument('--limit', type=int, help='Process only first N matches (for testing)')
    parser.add_argument('--dry-run', action='store_true', help='Simulate without writing files')
    parser.add_argument('--standings', action='store_true', help='Also extract standings data from Standings tab')
    parser.add_argument('--backfill-predictions', action='store_true', help='Fix region_league/crests in predictions.csv')
    parser.add_argument('--league-page', action='store_true', help='Harvest all match URLs from registered league pages')
    
    args = parser.parse_args()

    asyncio.run(enrich_all_schedules(
        limit=args.limit,
        dry_run=args.dry_run,
        extract_standings=args.standings,
        backfill_predictions=args.backfill_predictions,
        league_page=args.league_page
    ))
