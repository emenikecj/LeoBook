# fs_extractor.py: Shared ALL-tab match extraction for Flashscore.
# Part of LeoBook Modules — Flashscore
#
# Single source of truth for extracting matches from the Flashscore ALL tab.
# Used by: fs_live_streamer.py, fs_schedule.py

import asyncio
from playwright.async_api import Page
from Core.Intelligence.selector_manager import SelectorManager
from Core.Intelligence.aigo_suite import AIGOSuite


@AIGOSuite.aigo_retry(max_retries=2, delay=2.0)
async def expand_all_leagues(page: Page) -> int:
    """
    Expand ALL collapsed leagues by clicking only accordion buttons
    that have aria-expanded="false". Never toggles already-expanded leagues.
    """
    show_more_sel = SelectorManager.get_selector("fs_home_page", "expand_show_more_button") or ".wcl-accordion_7Fi80"

    total_expanded = 0
    max_rounds = 5

    for round_num in range(max_rounds):
        try:
            expanded_this_round = await page.evaluate(r"""(showMoreSel) => {
                let count = 0;
                // ONLY click collapsed accordion buttons (aria-expanded="false")
                document.querySelectorAll(showMoreSel).forEach(btn => {
                    if (btn.getAttribute('aria-expanded') === 'false') {
                        btn.click(); count++;
                    }
                });
                return count;
            }""", show_more_sel)

            total_expanded += expanded_this_round or 0
            print(f"    [Extractor] Expansion round {round_num+1}: expanded {expanded_this_round} collapsed leagues.")

            if not expanded_this_round:
                break  # All leagues expanded

            # Wait for DOM to settle after clicks
            await asyncio.sleep(1.5)

        except Exception as e:
            print(f"    [Extractor] Expansion round {round_num+1} warning: {e}")
            break

    if total_expanded:
        await asyncio.sleep(1)
    print(f"    [Extractor] Total expanded: {total_expanded} leagues across {round_num+1} rounds.")
    return total_expanded


@AIGOSuite.aigo_retry(max_retries=2, delay=3.0, context_key="fs_home_page", element_key="match_rows")
async def extract_all_matches(page: Page, label: str = "Extractor") -> list:
    """
    Extracts ALL matches from the Flashscore ALL tab.
    Uses SelectorManager selectors with container fallback for mobile.
    Returns list of match dicts.
    """
    selectors = SelectorManager.get_all_selectors_for_context("fs_home_page")
    await asyncio.sleep(3)

    result = await page.evaluate(r"""(sel) => {
        const matches = [];
        const debug = {total_elements: 0, headers: 0, headers_with_matches: 0, empty_headers: 0, no_id: 0, no_teams: 0, matched: 0};
        const combinedSel = sel.league_header_wrapper + ', ' + sel.match_rows;
        let container = document.querySelector(sel.sport_container_soccer);
        let allElements = container ? container.querySelectorAll(combinedSel) : [];
        if (allElements.length < 50) {
            container = document.body;
            allElements = container.querySelectorAll(combinedSel);
            debug.fallback = true;
        }
        debug.total_elements = allElements.length;

        let currentRegion = '';
        let currentLeague = '';
        let currentLeagueUrl = '';
        let currentRegionFlag = '';
        let matchesSinceLastHeader = 0;

        allElements.forEach((el) => {
            if (el.matches(sel.league_header_wrapper)) {
                // Track previous header's match count
                if (debug.headers > 0) {
                    if (matchesSinceLastHeader > 0) debug.headers_with_matches++;
                    else debug.empty_headers++;
                }
                matchesSinceLastHeader = 0;
                debug.headers++;
                const catEl = el.querySelector(sel.league_country_text);
                const titleEl = el.querySelector(sel.league_title_text);
                const linkEl = el.querySelector(sel.league_title_link);
                const flagEl = el.querySelector(sel.league_flag);

                currentRegion = catEl ? catEl.innerText.trim() : '';
                currentLeague = titleEl ? titleEl.innerText.trim() : '';
                currentLeagueUrl = linkEl ? linkEl.getAttribute('href') : '';
                currentRegionFlag = flagEl ? flagEl.className : '';
                return;
            }

            const rowId = el.getAttribute('id');
            const cleanId = rowId ? rowId.replace(sel.match_id_prefix, '') : null;
            if (!cleanId) { debug.no_id++; return; }

            const homeNameEl = el.querySelector(sel.match_row_home_team_name);
            const awayNameEl = el.querySelector(sel.match_row_away_team_name);
            if (!homeNameEl || !awayNameEl) { debug.no_teams++; return; }

            debug.matched++;
            matchesSinceLastHeader++;

            const homeScoreEl = el.querySelector(sel.live_match_home_score);
            const awayScoreEl = el.querySelector(sel.live_match_away_score);
            const stageEl = el.querySelector(sel.live_match_stage_block);
            const timeEl = el.querySelector(sel.match_row_time);
            const linkEl = el.querySelector(sel.event_row_link);
            const homeLogoEl = el.querySelector(sel.match_home_logo);
            const awayLogoEl = el.querySelector(sel.match_away_logo);

            const isLiveClass = el.classList.contains(sel.live_match_row.replace('.', ''));
            const stageText = stageEl ? stageEl.innerText.trim() : '';
            const stageLower = stageText.toLowerCase();
            const rawTimeRaw = timeEl ? timeEl.innerText.trim() : '';
            // FRO = Final Result Only (no livestream, delayed result announcement)
            const isFRO = /FRO/i.test(rawTimeRaw);
            const rawTime = rawTimeRaw.replace(/[\n\r]+/g, ' ').replace(/FRO/gi, '').trim();

            let status = 'scheduled';
            let stageDetail = '';
            let minute = '';
            let homeScore = homeScoreEl ? homeScoreEl.innerText.trim() : '';
            let awayScore = awayScoreEl ? awayScoreEl.innerText.trim() : '';

            // Content-based live detection fallback
            const liveStagePattern = /^(\d+['′+]?\s*$|half|break|ht$|pen|extra|et$|\d+\+\d+)/i;
            const isLiveContent = stageText && liveStagePattern.test(stageText.replace(/\s+/g, ''));
            const isLive = isLiveClass || isLiveContent;

            if (isLive) {
                status = 'live'; minute = stageText.replace(/\s+/g, '');
                const minLower = minute.toLowerCase();
                if (minLower === 'ht' || minLower.includes('half')) status = 'halftime';
                else if (minLower.includes('break')) status = 'break';
                else if (minLower.includes('pen')) { status = 'penalties'; stageDetail = 'Pen'; }
                else if (minLower.includes('et') && !minLower.match(/^\d/)) { status = 'extra_time'; stageDetail = 'ET'; }
            } else if (stageLower.includes('postp') || stageLower.includes('pp')) {
                status = 'postponed'; stageDetail = 'Postp'; homeScore = ''; awayScore = '';
            } else if (stageLower.includes('canc')) {
                status = 'cancelled'; stageDetail = 'Canc'; homeScore = ''; awayScore = '';
            } else if (stageLower.includes('abn') || stageLower.includes('abd')) {
                status = 'cancelled'; stageDetail = 'Abn'; homeScore = ''; awayScore = '';
            } else if (stageLower.includes('fro')) {
                status = 'finished'; stageDetail = 'FRO';
            } else if (stageLower.includes('susp')) {
                status = 'suspended'; stageDetail = 'Susp'; homeScore = ''; awayScore = '';
            } else if (homeScoreEl && awayScoreEl) {
                const scoreState = homeScoreEl.getAttribute('data-state');
                if (scoreState === sel.score_final_state || stageLower.includes('fin') || stageLower.includes('after') || stageLower === '') {
                    status = 'finished';
                    if (stageLower.includes('pen')) stageDetail = 'Pen';
                    else if (stageLower.includes('et')) stageDetail = 'AET';
                    else if (stageLower.includes('wo') || stageLower.includes('w.o')) stageDetail = 'WO';
                }
            }

            // If time column had FRO flag and no other status overrode it
            if (isFRO && status === 'scheduled') {
                status = 'fro';
                stageDetail = 'FRO';
            }

            // Team ID and URL extraction from match link
            let homeTeamId = '', awayTeamId = '', homeTeamUrl = '', awayTeamUrl = '';
            const mLink = linkEl ? linkEl.getAttribute('href') : '';
            if (mLink && mLink.includes('/match/football/')) {
                const cleanPath = mLink.replace(/^(.*\/match\/football\/)/, '');
                const parts = cleanPath.split('/').filter(p => p);
                if (parts.length >= 2) {
                    const hSeg = parts[0]; const aSeg = parts[1];
                    const hSlug = hSeg.substring(0, hSeg.lastIndexOf('-'));
                    homeTeamId = hSeg.substring(hSeg.lastIndexOf('-') + 1);
                    const aSlug = aSeg.substring(0, aSeg.lastIndexOf('-'));
                    awayTeamId = aSeg.substring(aSeg.lastIndexOf('-') + 1);

                    if (hSlug && homeTeamId) homeTeamUrl = `https://www.flashscore.com/team/${hSlug}/${homeTeamId}/`;
                    if (aSlug && awayTeamId) awayTeamUrl = `https://www.flashscore.com/team/${aSlug}/${awayTeamId}/`;
                }
            }

            // League Stage Splitting
            let cleanLeague = currentLeague;
            let leagueStage = '';
            const stageMatch = cleanLeague.match(/ - (Round \d+|Group [A-Z]|Play Offs|Qualification|Relegation Group|Championship Group|Finals?)$/i);
            if (stageMatch) {
                leagueStage = stageMatch[1];
                cleanLeague = cleanLeague.substring(0, stageMatch.index).trim();
            }

            const regionLeague = currentRegion ? currentRegion + ' - ' + cleanLeague : cleanLeague || 'Unknown';

            const cleanLeagueUrl = (currentLeagueUrl && !currentLeagueUrl.startsWith('http')) 
                ? 'https://www.flashscore.com' + currentLeagueUrl 
                : currentLeagueUrl;
            
            const cleanMatchLink = (mLink && !mLink.startsWith('http'))
                ? 'https://www.flashscore.com' + mLink
                : mLink;

            matches.push({
                fixture_id: cleanId,
                home_team: homeNameEl.innerText.trim(),
                away_team: awayNameEl.innerText.trim(),
                home_team_id: homeTeamId,
                away_team_id: awayTeamId,
                home_team_url: homeTeamUrl,
                away_team_url: awayTeamUrl,
                home_crest: homeLogoEl ? homeLogoEl.src : '',
                away_crest: awayLogoEl ? awayLogoEl.src : '',
                home_score: homeScore,
                away_score: awayScore,
                minute: minute,
                status: status,
                stage_detail: stageDetail,
                region_league: regionLeague,
                league_stage: leagueStage,
                league_url: cleanLeagueUrl,
                region_flag: currentRegionFlag,
                match_link: cleanMatchLink,
                match_time: rawTime,
                timestamp: new Date().toISOString()
            });
        });
        // Finalize last header's match count
        if (debug.headers > 0) {
            if (matchesSinceLastHeader > 0) debug.headers_with_matches++;
            else debug.empty_headers++;
        }
        return {matches, debug};
    }""", selectors)

    matches = result.get('matches', [])
    debug = result.get('debug', {})
    active = debug.get('headers_with_matches', 0)
    empty = debug.get('empty_headers', 0)
    print(f"   [{label}] Found {len(matches)} matches across {active} leagues. Debug: {debug}")
    if empty > 0:
        print(f"   [{label}] ⚠ {empty} league headers had no matches (finished/hidden).")

    return matches or []
