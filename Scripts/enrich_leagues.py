# enrich_leagues.py: Visit league pages to fill Unknown metadata in region_league, schedules, and teams CSVs.
# Part of LeoBook Scripts — Data Enrichment
#
# Functions: enrich_leagues()
# Called by: Leo.py (--enrich-leagues)

import asyncio
from datetime import datetime as dt
from playwright.async_api import async_playwright, Page, Browser

from Core.Utils.constants import MAX_CONCURRENCY
from Core.Browser.site_helpers import fs_universal_popup_dismissal
from Core.Intelligence.selector_manager import SelectorManager
from Core.Browser.Extractors.league_page_extractor import extract_league_metadata, extract_league_match_urls
from Data.Access.db_helpers import (
    CSV_LOCK, _read_csv, _write_csv, batch_upsert,
    REGION_LEAGUE_CSV, SCHEDULES_CSV, TEAMS_CSV,
    files_and_headers
)

CTX = "fs_league_page"


async def _extract_league_data(page: Page, league_row: dict) -> dict:
    """
    Visit a single league page, extract metadata + matches from Results and Fixtures tabs.
    Returns dict with keys: metadata, results_matches, fixtures_matches.
    """
    league_url = league_row.get("league_url", "").strip()
    league_id = league_row.get("league_id", "")
    if not league_url:
        return {}

    result = {"league_id": league_id, "metadata": {}, "match_ids": []}

    try:
        # 1. Navigate to league page
        await page.goto(league_url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)
        await fs_universal_popup_dismissal(page)

        # 2. Extract metadata (crest, flag, hash, region_url)
        metadata = await extract_league_metadata(page)
        result["metadata"] = metadata or {}
        
        # If hash was found, use it as the extracted_league_id
        extracted_league_id = metadata.get("league_id", "")

        # 3. Extract matches from Results tab
        results_urls = await extract_league_match_urls(page, league_url, mode="results")


        # 5. Extract matches from Fixtures tab
        fixtures_urls = await extract_league_match_urls(page, league_url, mode="fixtures")

        # Collect all unique fixture IDs from the match URLs
        all_match_ids = set()
        for url in (results_urls or []) + (fixtures_urls or []):
            # URLs look like /match/FIXTURE_ID/#/match-summary
            parts = url.strip("/").split("/")
            for i, p in enumerate(parts):
                if p == "match" and i + 1 < len(parts):
                    all_match_ids.add(parts[i + 1])
                    break

        result["match_ids"] = list(all_match_ids)

        # 6. Extract full team metadata from match rows (crest, URL, ID)
        match_row_sel = SelectorManager.get_selector(CTX, "match_row") or "[id^='g_1_']"
        home_sel = SelectorManager.get_selector(CTX, "home_participant") or ".event__homeParticipant"
        away_sel = SelectorManager.get_selector(CTX, "away_participant") or ".event__awayParticipant"
        name_sel = SelectorManager.get_selector(CTX, "team_name") or ".wcl-name_jjfMf"
        link_sel = SelectorManager.get_selector(CTX, "team_link") or "a[href*='/team/']"
        logo_sel = SelectorManager.get_selector(CTX, "team_logo") or "img"

        team_data = await page.evaluate(r"""(s) => {
            const teams = [];
            const seen = new Set();
            document.querySelectorAll(s.matchRowSel).forEach(row => {
                [s.homeSel, s.awaySel].forEach(side => {
                    const container = row.querySelector(side);
                    if (!container) return;
                    const nameEl = container.querySelector(s.nameSel);
                    const imgEl = container.querySelector(s.logoSel);
                    const linkEl = container.querySelector(s.linkSel);
                    const name = nameEl ? nameEl.innerText.trim() : '';
                    if (!name || seen.has(name)) return;
                    seen.add(name);

                    let teamId = '', teamUrl = '';
                    if (linkEl) {
                        teamUrl = linkEl.href || '';
                        const parts = teamUrl.replace(/\/$/, '').split('/');
                        teamId = parts[parts.length - 1] || '';
                    }
                    teams.push({
                        name, team_id: teamId, team_url: teamUrl,
                        crest: imgEl ? (imgEl.src || imgEl.getAttribute('data-src') || '') : ''
                    });
                });
            });
            return teams;
        }""", {"matchRowSel": match_row_sel, "homeSel": home_sel, "awaySel": away_sel,
               "nameSel": name_sel, "linkSel": link_sel, "logoSel": logo_sel})
        result["team_data"] = team_data or []

    except Exception as e:
        print(f"    [Enrich] Error processing {league_url}: {e}")

    return result


async def enrich_single_league(context, league_row: dict, sem: asyncio.Semaphore, i: int, total: int):
    """Worker task to process a single league."""
    async with sem:
        old_league_id = league_row.get("league_id", "?")
        league_name = league_row.get("league", "?")
        region = league_row.get("region", "?")
        print(f"\n  [{i}/{total}] {region} - {league_name} ({old_league_id})")

        page = await context.new_page()
        try:
            data = await _extract_league_data(page, league_row)
            if not data or not data.get("metadata"):
                print(f"    [Enrich] No metadata extracted for {league_name} — skipping.")
                return

            meta = data["metadata"]
            league_crest = meta.get("league_crest", "")
            region_flag = meta.get("region_flag", "")
            region_url = meta.get("region_url", "")
            new_league_id = meta.get("league_id", old_league_id)
            region_league_label = f"{region} - {league_name}"

            # --- Incremental write: update region_league.csv ---
            async with CSV_LOCK:
                all_leagues = _read_csv(REGION_LEAGUE_CSV)
                updated_league = False
                for row in all_leagues:
                    if row.get("league_id") == old_league_id:
                        if league_crest and league_crest != "Unknown":
                            row["league_crest"] = league_crest
                        if region_flag and region_flag != "Unknown":
                            row["region_flag"] = region_flag
                        if region_url:
                            row["region_url"] = region_url
                        if new_league_id and new_league_id != old_league_id:
                            row["league_id"] = new_league_id
                        row["last_updated"] = dt.now().isoformat()
                        row["date_updated"] = dt.now().isoformat()
                        updated_league = True
                        break
                
                if updated_league:
                    _write_csv(REGION_LEAGUE_CSV, all_leagues, files_and_headers[REGION_LEAGUE_CSV])
                    print(f"    [Enrich] [DISK] Updated region_league.csv for {league_name}")
                else:
                    print(f"    [Enrich] [DISK] Warning: Could not find league_id {old_league_id} in region_league.csv")

            # --- Incremental write: backfill schedules.csv ---
            if match_ids:
                async with CSV_LOCK:
                    all_schedules = _read_csv(SCHEDULES_CSV)
                    fid_set = set(match_ids)
                    sched_updated = 0
                    for row in all_schedules:
                        fid = row.get("fixture_id", "")
                        if fid in fid_set:
                            changed = False
                            if row.get("league_id", "Unknown") == "Unknown" or row.get("league_id") == old_league_id:
                                row["league_id"] = new_league_id
                                changed = True
                            if row.get("region_league", "Unknown") == "Unknown":
                                row["region_league"] = region_league_label
                                changed = True
                            if changed:
                                row["last_updated"] = dt.now().isoformat()
                                sched_updated += 1
                    if sched_updated:
                        _write_csv(SCHEDULES_CSV, all_schedules, files_and_headers[SCHEDULES_CSV])
                        print(f"    [Enrich] [DISK] Backfilled {sched_updated} schedules with league_id={new_league_id}")

            # --- Incremental write: backfill teams.csv ---
            team_data = data.get("team_data", [])
            if team_data:
                async with CSV_LOCK:
                    all_teams = _read_csv(TEAMS_CSV)
                    team_map = {t["team_id"]: t for t in team_data if t.get("team_id")}
                    teams_updated = 0
                    for row in all_teams:
                        tid = row.get("team_id", "")
                        if tid in team_map:
                            update = team_map[tid]
                            changed = False
                            if not row.get("team_crest") and update.get("crest"):
                                row["team_crest"] = update["crest"]
                                changed = True
                            if not row.get("team_url") and update.get("team_url"):
                                row["team_url"] = update["team_url"]
                                changed = True
                            current_lids = row.get("league_ids", "")
                            if new_league_id not in current_lids:
                                if not current_lids or current_lids == "Unknown":
                                    row["league_ids"] = new_league_id
                                else:
                                    row["league_ids"] = f"{current_lids},{new_league_id}"
                                changed = True
                            if changed:
                                row["last_updated"] = dt.now().isoformat()
                                teams_updated += 1
                    if teams_updated:
                        _write_csv(TEAMS_CSV, all_teams, files_and_headers[TEAMS_CSV])

            teams_found = len(team_data)
            status = (f"ID={new_league_id[:6]}... crest={'✓' if league_crest else '✗'} "
                      f"flag={'✓' if region_flag else '✗'} matches={len(match_ids)} teams={teams_found}")
            print(f"    [Enrich] Done: {region_league_label} -> {status}")

        finally:
            await page.close()


async def enrich_leagues():
    """
    Main entry point: Parallel league enrichment using MAX_CONCURRENCY.
    """
    # 1. Read leagues needing enrichment
    all_leagues = _read_csv(REGION_LEAGUE_CSV)
    needs_enrichment = [
        row for row in all_leagues
        if row.get("region_flag", "Unknown") == "Unknown"
        or row.get("league_crest", "Unknown") == "Unknown"
        or row.get("region_url", "") == ""
        or len(row.get("league_id", "")) > 20
    ]

    if not needs_enrichment:
        print("  [Enrich] All leagues already have metadata. Nothing to do.")
        return

    print(f"\n  [Enrich] Found {len(needs_enrichment)} leagues needing metadata enrichment.")
    print(f"  [Enrich] Concurrency: {MAX_CONCURRENCY}")

    # 2. Launch browser
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Mobile Safari/537.36"
            ),
            viewport={"width": 450, "height": 900},
            timezone_id="Africa/Lagos"
        )

        sem = asyncio.Semaphore(MAX_CONCURRENCY)
        tasks = []
        for i, league_row in enumerate(needs_enrichment, 1):
            tasks.append(enrich_single_league(context, league_row, sem, i, len(needs_enrichment)))

        await asyncio.gather(*tasks)

        await context.close()
        await browser.close()

    print(f"\n  [Enrich] ✅ League enrichment complete.")


# ================================================
# Per-Match Inline League Enrichment (v3.6)
# ================================================

async def enrich_league_inline(page, league_url: str, league_id: str, league_name: str = "", region: str = ""):
    """
    Per-match league enrichment: uses an ALREADY OPEN page to visit a league page,
    extract metadata + match URLs + team data, and persist immediately.
    
    Called from fs_processor.py after match page metadata extraction.
    Returns dict of extracted data or empty dict on failure.
    """
    if not league_url or not league_id:
        return {}

    league_row = {
        "league_url": league_url,
        "league_id": league_id,
        "league": league_name,
        "region": region
    }

    result = {"league_id": league_id, "metadata": {}, "match_ids": [], "team_data": []}

    try:
        # 1. Navigate to league page
        await page.goto(league_url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)

        from Core.Browser.site_helpers import fs_universal_popup_dismissal
        await fs_universal_popup_dismissal(page)

        # 2. Extract metadata (crest, flag, hash, region_url)
        from Core.Browser.Extractors.league_page_extractor import extract_league_metadata, extract_league_match_urls
        metadata = await extract_league_metadata(page)
        result["metadata"] = metadata or {}

        # 3. Extract matches from Results + Fixtures tabs
        results_urls = await extract_league_match_urls(page, league_url, mode="results")
        fixtures_urls = await extract_league_match_urls(page, league_url, mode="fixtures")

        all_match_ids = set()
        for url in (results_urls or []) + (fixtures_urls or []):
            parts = url.strip("/").split("/")
            for i, p in enumerate(parts):
                if p == "match" and i + 1 < len(parts):
                    all_match_ids.add(parts[i + 1])
                    break
        result["match_ids"] = list(all_match_ids)

        # 4. Extract team data from match rows on league page
        match_row_sel = SelectorManager.get_selector(CTX, "match_row") or "[id^='g_1_']"
        home_sel = SelectorManager.get_selector(CTX, "home_participant") or ".event__homeParticipant"
        away_sel = SelectorManager.get_selector(CTX, "away_participant") or ".event__awayParticipant"
        name_sel = SelectorManager.get_selector(CTX, "team_name") or ".wcl-name_jjfMf"
        link_sel = SelectorManager.get_selector(CTX, "team_link") or "a[href*='/team/']"
        logo_sel = SelectorManager.get_selector(CTX, "team_logo") or "img"

        team_data = await page.evaluate(r"""(s) => {
            const teams = [];
            const seen = new Set();
            document.querySelectorAll(s.matchRowSel).forEach(row => {
                [s.homeSel, s.awaySel].forEach(side => {
                    const container = row.querySelector(side);
                    if (!container) return;
                    const nameEl = container.querySelector(s.nameSel);
                    const imgEl = container.querySelector(s.logoSel);
                    const linkEl = container.querySelector(s.linkSel);
                    const name = nameEl ? nameEl.innerText.trim() : '';
                    if (!name || seen.has(name)) return;
                    seen.add(name);
                    let teamId = '', teamUrl = '';
                    if (linkEl) {
                        teamUrl = linkEl.href || '';
                        const parts = teamUrl.replace(/\/$/, '').split('/');
                        teamId = parts[parts.length - 1] || '';
                    }
                    teams.push({
                        name, team_id: teamId, team_url: teamUrl,
                        crest: imgEl ? (imgEl.src || imgEl.getAttribute('data-src') || '') : ''
                    });
                });
            });
            return teams;
        }""", {"matchRowSel": match_row_sel, "homeSel": home_sel, "awaySel": away_sel,
               "nameSel": name_sel, "linkSel": link_sel, "logoSel": logo_sel})
        result["team_data"] = team_data or []

    except Exception as e:
        print(f"    [Enrich Inline] Error processing {league_url}: {e}")
        return result

    # --- Persist to CSVs under lock ---
    meta = result.get("metadata", {})
    league_crest = meta.get("league_crest", "")
    region_flag = meta.get("region_flag", "")
    region_url = meta.get("region_url", "")
    new_league_id = meta.get("league_id", league_id)

    # Update region_league.csv
    async with CSV_LOCK:
        all_leagues = _read_csv(REGION_LEAGUE_CSV)
        updated = False
        for row in all_leagues:
            if row.get("league_id") == league_id:
                if league_crest and league_crest != "Unknown":
                    row["league_crest"] = league_crest
                if region_flag and region_flag != "Unknown":
                    row["region_flag"] = region_flag
                if region_url:
                    row["region_url"] = region_url
                if new_league_id and new_league_id != league_id:
                    row["league_id"] = new_league_id
                row["last_updated"] = dt.now().isoformat()
                row["date_updated"] = dt.now().isoformat()
                updated = True
                break
        if updated:
            _write_csv(REGION_LEAGUE_CSV, all_leagues, files_and_headers[REGION_LEAGUE_CSV])
            print(f"    [Enrich Inline] ✓ League '{league_name}' metadata saved")

    # Backfill schedules.csv
    match_ids = result.get("match_ids", [])
    region_league_label = f"{region} - {league_name}" if region else league_name
    if match_ids:
        async with CSV_LOCK:
            all_schedules = _read_csv(SCHEDULES_CSV)
            fid_set = set(match_ids)
            sched_updated = 0
            for row in all_schedules:
                fid = row.get("fixture_id", "")
                if fid in fid_set:
                    if row.get("league_id", "Unknown") == "Unknown" or row.get("league_id") == league_id:
                        row["league_id"] = new_league_id
                        row["last_updated"] = dt.now().isoformat()
                        sched_updated += 1
            if sched_updated:
                _write_csv(SCHEDULES_CSV, all_schedules, files_and_headers[SCHEDULES_CSV])
                print(f"    [Enrich Inline] ✓ Backfilled {sched_updated} schedules")

    # Backfill teams.csv
    team_data_list = result.get("team_data", [])
    if team_data_list:
        async with CSV_LOCK:
            all_teams = _read_csv(TEAMS_CSV)
            team_map = {t["team_id"]: t for t in team_data_list if t.get("team_id")}
            teams_updated = 0
            for row in all_teams:
                tid = row.get("team_id", "")
                if tid in team_map:
                    update = team_map[tid]
                    changed = False
                    if not row.get("team_crest") and update.get("crest"):
                        row["team_crest"] = update["crest"]
                        changed = True
                    if not row.get("team_url") and update.get("team_url"):
                        row["team_url"] = update["team_url"]
                        changed = True
                    current_lids = row.get("league_ids", "")
                    if new_league_id not in current_lids:
                        row["league_ids"] = f"{current_lids},{new_league_id}" if current_lids and current_lids != "Unknown" else new_league_id
                        changed = True
                    if changed:
                        row["last_updated"] = dt.now().isoformat()
                        teams_updated += 1
            if teams_updated:
                _write_csv(TEAMS_CSV, all_teams, files_and_headers[TEAMS_CSV])
                print(f"    [Enrich Inline] ✓ Backfilled {teams_updated} teams")

    print(f"    [Enrich Inline] Complete: matches={len(match_ids)} teams={len(team_data_list)}")
    return result
