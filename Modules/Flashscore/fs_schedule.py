# fs_schedule.py: fs_schedule.py: Daily match list extraction for Flashscore.
# Part of LeoBook Modules — Flashscore
#
# Functions: extract_matches_from_page()

import asyncio
from typing import List, Dict, Any
from playwright.async_api import Page
from Core.Intelligence.selector_manager import SelectorManager
from Data.Access.db_helpers import save_schedule_entry, save_team_entry
from Data.Access.sync_manager import SyncManager

async def extract_matches_from_page(page: Page) -> list:
    """
    Executes JavaScript on the page to extract all match data for the visible day.
    """
    print("    [Extractor] Extracting match data from page...")

    # --- Bulk JS expand collapsed leagues (single call, no sequential clicks) ---
    try:
        down_arrow_sel = SelectorManager.get_selector("fs_home_page", "league_expand_icon_collapsed")
        expanded = await page.evaluate(r"""(arrowSel) => {
            // Method 1: Click collapsed arrow icons (same as streamer)
            const arrows = document.querySelectorAll(arrowSel);
            let count = 0;
            arrows.forEach(a => {
                const header = a.closest('[class*="event__header"]') || a.parentElement;
                if (header) { header.click(); count++; }
            });
            // Method 2: Also expand "Show More" accordion buttons
            document.querySelectorAll('.wcl-accordion_7Fi80').forEach(btn => {
                btn.click(); count++;
            });
            return count;
        }""", down_arrow_sel)
        if expanded:
            print(f"    [Extractor] Bulk-expanded {expanded} collapsed leagues.")
            await asyncio.sleep(1)
    except Exception as e:
        print(f"    [Extractor] Expansion warning: {e}")

    selectors = SelectorManager.get_all_selectors_for_context("fs_home_page")

    result = await page.evaluate(
        r"""(sel) => {
            const matches = [];
            const debug = {total: 0, headers: 0, no_id: 0, no_teams: 0, matched: 0, skipped_league: 0};

            const headerSel = sel.league_header_wrapper || '.event__header';
            const matchSel  = sel.match_rows || '.event__match';
            const combinedSel = headerSel + ', ' + matchSel;

            // Container fallback: .sportName.soccer may only wrap a subset on mobile
            let container = document.querySelector(sel.sport_container_soccer);
            let allElements = container ? container.querySelectorAll(combinedSel) : [];
            if (allElements.length < 50) {
                container = document.body;
                allElements = container.querySelectorAll(combinedSel);
                debug.fallback = true;
            }
            debug.total = allElements.length;

            let currentRegionLeague = 'Unknown';
            let skipCurrentLeague = false;

            allElements.forEach((el) => {
                // 1. League Header
                if (el.matches(headerSel)) {
                    debug.headers++;
                    const regionEl = el.querySelector(sel.league_country_text) || el.querySelector('.event__title--type');
                    const leagueEl = el.querySelector(sel.league_title_text) || el.querySelector('.event__title--name');

                    if (regionEl && leagueEl) {
                        currentRegionLeague = regionEl.innerText.trim() + ' - ' + leagueEl.innerText.trim();
                    } else {
                        currentRegionLeague = el.innerText.trim().replace(/[\r\n]+/g, ' - ');
                    }

                    const headerText = el.innerText.toLowerCase();
                    skipCurrentLeague = headerText.includes('draw') || headerText.includes('promoted') || headerText.includes('results');
                    return;
                }

                // 2. Match Row
                if (skipCurrentLeague) { debug.skipped_league++; return; }

                const rowId = el.getAttribute('id');
                const cleanId = rowId ? rowId.replace(sel.match_id_prefix || 'g_1_', '') : null;
                if (!cleanId) { debug.no_id++; return; }

                const homeEl = el.querySelector(sel.match_row_home_team_name)
                            || el.querySelector('.event__homeParticipant');
                const awayEl = el.querySelector(sel.match_row_away_team_name)
                            || el.querySelector('.event__awayParticipant');
                if (!homeEl || !awayEl) { debug.no_teams++; return; }

                const timeEl = el.querySelector(sel.match_row_time || '.event__time');
                const stageEl = el.querySelector(sel.live_match_stage_block)
                             || el.querySelector('.event__stage');
                const linkEl = el.querySelector(sel.event_row_link || 'a.eventRowLink');

                const rawTime = timeEl ? timeEl.innerText.trim() : '';
                const rawStage = stageEl ? stageEl.innerText.trim() : '';

                let matchStatus = 'scheduled';
                let matchTime = rawTime || 'N/A';

                const lowerStage = rawStage.toLowerCase();
                if (lowerStage.includes('postp')) matchStatus = 'postponed';
                else if (lowerStage.includes('canc')) matchStatus = 'cancelled';
                else if (lowerStage.includes('abn') || lowerStage.includes('abd')) matchStatus = 'abandoned';
                else if (lowerStage.includes('del')) matchStatus = 'delayed';
                else if (!rawTime && !rawStage) matchStatus = 'untimed';
                else if (rawStage && !rawTime) matchStatus = rawStage.toLowerCase();

                const matchLink = linkEl ? linkEl.getAttribute('href') : '';

                debug.matched++;
                matches.push({
                    fixture_id: cleanId,
                    match_link: matchLink,
                    home_team: homeEl.innerText.trim(),
                    away_team: awayEl.innerText.trim(),
                    match_time: matchTime,
                    region_league: currentRegionLeague,
                    status: matchStatus,
                    last_updated: new Date().toISOString()
                });
            });
            return {matches, debug};
        }""", selectors)

    matches = result.get('matches', [])
    debug = result.get('debug', {})
    print(f"    [Extractor] Found {len(matches)} matches. Debug: {debug}")

    # Partial Sync Integration: Local Save + Supabase Upsert
    if matches:
        print(f"    [Extractor] Pairings complete. Saving {len(matches)} fixtures and teams...")
        sync = SyncManager()
        
        teams_to_sync = []
        for m in matches:
            # 1. Save Schedule
            save_schedule_entry(m)
            
            # 2. Extract and Save Teams (Metadata Capture)
            # Use fixture_id as a hint for team IDs if extraction failed, or just use names as keys
            home_team = {
                'team_id': m.get('home_team_id') or f"t_{hash(m['home_team']) & 0xfffffff}",
                'team_name': m['home_team'],
                'region': m['region_league'].split(' - ')[0] if ' - ' in m['region_league'] else 'Unknown'
            }
            away_team = {
                'team_id': m.get('away_team_id') or f"t_{hash(m['away_team']) & 0xfffffff}",
                'team_name': m['away_team'],
                'region': m['region_league'].split(' - ')[0] if ' - ' in m['region_league'] else 'Unknown'
            }
            
            save_team_entry(home_team)
            save_team_entry(away_team)
            teams_to_sync.extend([home_team, away_team])
        
        # 3. Sync to Cloud
        if sync.supabase:
            print(f"    [Cloud] Upserting {len(matches)} schedules and {len(teams_to_sync)} teams...")
            await sync.batch_upsert('schedules', matches)
            # Deduplicate teams before sync
            unique_teams = list({t['team_id']: t for t in teams_to_sync}.values())
            await sync.batch_upsert('teams', unique_teams)
            print(f"    [SUCCESS] Multi-table synchronization complete.")

    return matches
