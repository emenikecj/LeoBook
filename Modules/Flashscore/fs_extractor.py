# fs_extractor.py: Shared ALL-tab match extraction for Flashscore.
# Part of LeoBook Modules — Flashscore
#
# Single source of truth for extracting matches from the Flashscore ALL tab.
# Used by: fs_live_streamer.py, fs_schedule.py

import asyncio
from playwright.async_api import Page
from Core.Intelligence.selector_manager import SelectorManager


async def expand_all_leagues(page: Page) -> int:
    """Bulk-expand all collapsed leagues via a single JS call."""
    try:
        down_arrow_sel = SelectorManager.get_selector("fs_home_page", "league_expand_icon_collapsed")
        expanded = await page.evaluate(r"""(arrowSel) => {
            const arrows = document.querySelectorAll(arrowSel);
            let count = 0;
            arrows.forEach(a => {
                const header = a.closest('[class*="event__header"]') || a.parentElement;
                if (header) { header.click(); count++; }
            });
            document.querySelectorAll('.wcl-accordion_7Fi80').forEach(btn => {
                btn.click(); count++;
            });
            return count;
        }""", down_arrow_sel)
        if expanded:
            await asyncio.sleep(1)
        return expanded or 0
    except Exception as e:
        print(f"    [Extractor] Expansion warning: {e}")
        return 0


async def extract_all_matches(page: Page, label: str = "Extractor") -> list:
    """
    Extracts ALL matches from the Flashscore ALL tab.
    Uses SelectorManager selectors with container fallback for mobile.
    Returns list of match dicts.
    """
    selectors = SelectorManager.get_all_selectors_for_context("fs_home_page")

    result = await page.evaluate(r"""(sel) => {
        const matches = [];
        const debug = {total_elements: 0, headers: 0, no_id: 0, no_teams: 0, matched: 0};
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

        allElements.forEach((el) => {
            if (el.matches(sel.league_header_wrapper)) {
                debug.headers++;
                const catEl = el.querySelector(sel.league_country_text);
                const titleEl = el.querySelector(sel.league_title_text);
                currentRegion = catEl ? catEl.innerText.trim() : '';
                currentLeague = titleEl ? titleEl.innerText.trim() : '';
                return;
            }

            const rowId = el.getAttribute('id');
            const cleanId = rowId ? rowId.replace(sel.match_id_prefix, '') : null;
            if (!cleanId) { debug.no_id++; return; }

            const homeNameEl = el.querySelector(sel.match_row_home_team_name);
            const awayNameEl = el.querySelector(sel.match_row_away_team_name);
            if (!homeNameEl || !awayNameEl) { debug.no_teams++; return; }

            debug.matched++;

            const homeScoreEl = el.querySelector(sel.live_match_home_score);
            const awayScoreEl = el.querySelector(sel.live_match_away_score);
            const stageEl = el.querySelector(sel.live_match_stage_block);
            const timeEl = el.querySelector(sel.match_row_time);
            const linkEl = el.querySelector(sel.event_row_link);

            const isLiveClass = el.classList.contains(sel.live_match_row.replace('.', ''));
            const stageText = stageEl ? stageEl.innerText.trim() : '';
            const stageLower = stageText.toLowerCase();
            const rawTime = timeEl ? timeEl.innerText.trim() : '';

            let status = 'scheduled';
            let stageDetail = '';
            let minute = '';
            let homeScore = homeScoreEl ? homeScoreEl.innerText.trim() : '';
            let awayScore = awayScoreEl ? awayScoreEl.innerText.trim() : '';

            // Content-based live detection fallback: if stage shows a minute number
            // (e.g. "45", "90+2") or live keywords, treat as live even without CSS class
            const minutePattern = /^\d+['′+]?$/;
            const liveStagePattern = /^(\d+['′+]?\s*$|half|break|ht$|pen|extra|et$|\d+\+\d+)/i;
            const isLiveContent = stageText && liveStagePattern.test(stageText.replace(/\s+/g, ''));
            const isLive = isLiveClass || isLiveContent;

            if (isLive) {
                status = 'live';
                minute = stageText.replace(/\s+/g, '');
                const minLower = minute.toLowerCase();
                if (minLower === 'ht' || minLower.includes('half')) status = 'halftime';
                else if (minLower.includes('break')) status = 'break';
                else if (minLower.includes('pen')) { status = 'penalties'; stageDetail = 'Pen'; }
                else if (minLower.includes('et') && !minLower.match(/^\d/)) { status = 'extra_time'; stageDetail = 'ET'; }
            } else if (stageLower.includes('postp') || stageLower.includes('pp')) {
                status = 'postponed'; stageDetail = 'Postp';
                homeScore = ''; awayScore = '';
            } else if (stageLower.includes('canc')) {
                status = 'cancelled'; stageDetail = 'Canc';
                homeScore = ''; awayScore = '';
            } else if (stageLower.includes('abn') || stageLower.includes('abd')) {
                status = 'cancelled'; stageDetail = 'Abn';
                homeScore = ''; awayScore = '';
            } else if (stageLower.includes('fro') || stageLower.includes('susp')) {
                status = 'fro'; stageDetail = 'FRO';
                homeScore = ''; awayScore = '';
            } else if (homeScoreEl && awayScoreEl) {
                const scoreState = homeScoreEl.getAttribute('data-state');
                if (scoreState === sel.score_final_state || stageLower.includes('fin') || stageLower === '') {
                    status = 'finished';
                    if (stageLower.includes('pen')) stageDetail = 'Pen';
                    else if (stageLower.includes('aet') || stageLower.includes('et')) stageDetail = 'AET';
                    else if (stageLower.includes('wo') || stageLower.includes('w.o')) stageDetail = 'WO';
                }
            }

            const regionLeague = currentRegion
                ? currentRegion + ' - ' + currentLeague
                : currentLeague || 'Unknown';

            matches.push({
                fixture_id: cleanId,
                home_team: homeNameEl.innerText.trim(),
                away_team: awayNameEl.innerText.trim(),
                home_score: homeScore,
                away_score: awayScore,
                minute: minute,
                status: status,
                stage_detail: stageDetail,
                region_league: regionLeague,
                match_link: linkEl ? linkEl.getAttribute('href') : '',
                match_time: rawTime,
                timestamp: new Date().toISOString()
            });
        });
        return {matches, debug};
    }""", selectors)

    matches = result.get('matches', [])
    debug = result.get('debug', {})
    print(f"   [{label}] Found {len(matches)} matches. Debug: {debug}")

    return matches or []
