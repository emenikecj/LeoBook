# fs_schedule.py: Daily match list extraction for Flashscore.
# Refactored for Clean Architecture (v2.7)
# This script scrapes upcoming fixtures and their relative URLs.

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

    # --- TIER 1: Bulk JS expand collapsed "Show More" buttons ---
    try:
        expanded = await page.evaluate("""() => {
            const containers = document.querySelectorAll('.wclIcon__leagueShowMoreCont');
            let clicked = 0;
            containers.forEach(cont => {
                const trigger = cont.querySelector('.wcl-trigger_CGiIV[data-state="delayed-open"]');
                if (trigger) {
                    const btn = trigger.querySelector('button.wcl-accordion_7Fi80');
                    if (btn) { btn.click(); clicked++; }
                }
            });
            return clicked;
        }""")
        if expanded:
            print(f"    [Extractor] Tier 1: Expanded {expanded} collapsed leagues via JS")
            await asyncio.sleep(1)
    except Exception:
        pass

    # --- TIER 2: Verify & retry with Playwright locator clicks on actual buttons ---
    try:
        still_collapsed = await page.evaluate("""() => {
            let count = 0;
            document.querySelectorAll('.wclIcon__leagueShowMoreCont').forEach(cont => {
                if (cont.querySelector('.wcl-trigger_CGiIV[data-state="delayed-open"]')) count++;
            });
            return count;
        }""")
        if still_collapsed > 0:
            print(f"    [Extractor] Tier 2: {still_collapsed} leagues still collapsed — retrying with locator clicks...")
            expand_buttons = page.locator('.wclIcon__leagueShowMoreCont .wcl-trigger_CGiIV[data-state="delayed-open"] button.wcl-accordion_7Fi80')
            count = await expand_buttons.count()
            for i in range(min(count, 50)):  # Safety cap
                try:
                    btn = expand_buttons.nth(i)
                    await btn.scroll_into_view_if_needed()
                    await btn.click(force=True, timeout=3000)
                    await asyncio.sleep(0.5)
                except Exception:
                    continue
            if count > 0:
                print(f"    [Extractor] Tier 2: Clicked {min(count, 50)} remaining expand buttons")
                await asyncio.sleep(1)
    except Exception:
        pass

    selectors = {
        "match_rows": SelectorManager.get_selector("fs_home_page", "match_rows"),
        "match_row_home_team_name": SelectorManager.get_selector("fs_home_page", "match_row_home_team_name"),
        "match_row_away_team_name": SelectorManager.get_selector("fs_home_page", "match_row_away_team_name"),
        "league_header": SelectorManager.get_selector("fs_home_page", "league_header"),
        "league_category": SelectorManager.get_selector("fs_home_page", "league_category"),
        "league_title": SelectorManager.get_selector("fs_home_page", "league_title_link"),
    }

    matches = await page.evaluate(
        r"""(selectors) => {
            const matches = [];
            const container = document.querySelector('.sportName.soccer') || document.querySelector('#live-table');
            if (!container) return [];

            let currentRegionLeague = 'Unknown';
            let skipCurrentLeague = false;

            // State-based iteration: process children in DOM order
            Array.from(container.children).forEach((el) => {
                // 1. Detect League Header (State change)
                if (el.classList.contains('event__header')) {
                    const regionEl = el.querySelector('.event__title--type');
                    const leagueEl = el.querySelector('.event__title--name');
                    
                    if (regionEl && leagueEl) {
                        currentRegionLeague = regionEl.innerText.trim() + ' - ' + leagueEl.innerText.trim();
                    } else {
                        currentRegionLeague = el.innerText.trim().replace(/[\r\n]+/g, ' - ');
                    }
                    
                    const headerText = el.innerText.toLowerCase();
                    skipCurrentLeague = headerText.includes('draw') || headerText.includes('promoted') || headerText.includes('results');
                    return;
                }

                // 2. Detect Match Row (Action based on state)
                if (el.classList.contains('event__match')) {
                    if (skipCurrentLeague) return;

                    const rowId = el.getAttribute('id');
                    const cleanId = rowId ? rowId.replace('g_1_', '') : null;
                    if (!cleanId) return;

                    const homeEl = el.querySelector('.event__homeParticipant .wcl-name_jjfMf') || el.querySelector('.event__homeParticipant') || el.querySelector('.event__participant--home');
                    const awayEl = el.querySelector('.event__awayParticipant .wcl-name_jjfMf') || el.querySelector('.event__awayParticipant') || el.querySelector('.event__participant--away');
                    const timeEl = el.querySelector('.event__time');
                    const stageEl = el.querySelector('.event__stage') || el.querySelector('.event__status');
                    const linkEl = el.querySelector('a.eventRowLink') || el.querySelector('a');

                    if (homeEl && awayEl && linkEl) {
                        const rawTime = timeEl ? timeEl.innerText.trim() : '';
                        const rawStage = stageEl ? stageEl.innerText.trim() : '';
                        
                        let matchStatus = 'scheduled';
                        let matchTime = rawTime || 'N/A';

                        // Advanced Status Logic
                        const lowerStage = rawStage.toLowerCase();
                        if (lowerStage.includes('postp')) matchStatus = 'postponed';
                        else if (lowerStage.includes('cancl')) matchStatus = 'cancelled';
                        else if (lowerStage.includes('abdn') || lowerStage.includes('aban')) matchStatus = 'abandoned';
                        else if (lowerStage.includes('del')) matchStatus = 'delayed';
                        else if (!rawTime && !rawStage) matchStatus = 'untimed';
                        else if (rawStage && !rawTime) matchStatus = rawStage.toLowerCase();

                        const matchLink = linkEl.getAttribute('href');
                        let homeTeamId = null, awayTeamId = null;

                        if (matchLink) {
                            const parts = matchLink.split('/').filter(p => p);
                            // Flashscore format: /match/home-away/ID/ or /match/slug/ID/
                            // We attempt to extract a stable ID if possible
                        }

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
                    }
                }
                
                // 3. Spacers/Ads are naturally skipped as they don't match the above classes
            });
            return matches;
        }""", selectors)

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
