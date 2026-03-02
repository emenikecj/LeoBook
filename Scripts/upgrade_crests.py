# upgrade_crests.py: Upgrade team crests in SQLite to use high-quality logos from Modules/Assets/logos.
# Part of LeoBook Scripts — Data Enhancement
#
# Functions: build_logo_index(), match_team_to_logo(), upgrade_all_crests()
# Called by: Leo.py (--upgrade-crests)
#
# Uses fuzzy matching to map team names in the DB to high-quality logo files.
# Prefers 512x512 PNGs for the best quality/size balance. Falls back to Flashscore crests.

import os
import re
import sqlite3
from typing import Optional, Dict, Tuple

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGOS_DIR = os.path.join(BASE_DIR, "Modules", "Assets", "logos")
DB_PATH = os.path.join(BASE_DIR, "Data", "Store", "leobook.db")
PREFERRED_RES = "512x512"  # Best balance of quality and file size


def _normalize(name: str) -> str:
    """Normalize a name for fuzzy comparison: lowercase, strip suffixes, remove accents."""
    s = name.lower().strip()
    # Remove common suffixes
    for suffix in [" fc", " cf", " sc", " ac", " afc", " ssc", " fk", " sk", " bk",
                   " united", " city", " town", " wanderers", " rovers",
                   " hotspur", " albion", " athletic", " villa",
                   " 1907", " 1908", " 1899", " 1898", " 1903", " 1911"]:
        if s.endswith(suffix):
            s = s[:-len(suffix)].strip()
    # Remove non-alphanumeric except spaces
    s = re.sub(r"[^a-z0-9\s]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _slug_to_name(slug: str) -> str:
    """Convert a logo filename slug back to a normalized name for matching."""
    # e.g. "manchester-city.football-logos.cc" -> "manchester city"
    name = slug.replace(".football-logos.cc", "")
    name = name.replace("-", " ")
    return _normalize(name)


def build_logo_index() -> Dict[str, Dict[str, str]]:
    """
    Build an index of all available logos.
    Returns: { normalized_team_name: { "svg": path, "512x512": path, ... } }
    """
    index = {}

    if not os.path.isdir(LOGOS_DIR):
        print(f"  [!] Logos directory not found: {LOGOS_DIR}")
        return index

    for league_dir in os.listdir(LOGOS_DIR):
        league_path = os.path.join(LOGOS_DIR, league_dir)
        if not os.path.isdir(league_path):
            continue

        # Index SVGs in root
        for f in os.listdir(league_path):
            if f.endswith(".svg"):
                slug = f.replace(".svg", "")
                norm_name = _slug_to_name(slug)
                if norm_name not in index:
                    index[norm_name] = {"league": league_dir}
                index[norm_name]["svg"] = os.path.join(league_path, f)

        # Index PNGs in resolution subdirs
        for res_dir in os.listdir(league_path):
            res_path = os.path.join(league_path, res_dir)
            if not os.path.isdir(res_path):
                continue
            for f in os.listdir(res_path):
                if f.endswith(".png"):
                    slug = f.replace(".png", "")
                    norm_name = _slug_to_name(slug)
                    if norm_name not in index:
                        index[norm_name] = {"league": league_dir}
                    index[norm_name][res_dir] = os.path.join(res_path, f)

    return index


def match_team_to_logo(team_name: str, index: Dict) -> Optional[str]:
    """
    Try to match a team name to a logo in the index.
    Returns the path to the preferred resolution, or None.
    """
    norm = _normalize(team_name)

    # Direct match
    if norm in index:
        entry = index[norm]
        return entry.get(PREFERRED_RES) or entry.get("svg") or next(
            (v for k, v in entry.items() if k not in ("league",)), None
        )

    # Partial match: check if any index key contains or is contained by the team name
    for key, entry in index.items():
        # Either direction substring match
        if key in norm or norm in key:
            return entry.get(PREFERRED_RES) or entry.get("svg") or next(
                (v for k, v in entry.items() if k not in ("league",)), None
            )

    # Word overlap match (at least 2 words in common, or single-word exact)
    norm_words = set(norm.split())
    for key, entry in index.items():
        key_words = set(key.split())
        overlap = norm_words & key_words
        if len(overlap) >= 1 and (len(overlap) >= 2 or len(key_words) == 1):
            return entry.get(PREFERRED_RES) or entry.get("svg") or next(
                (v for k, v in entry.items() if k not in ("league",)), None
            )

    return None


def upgrade_all_crests(limit: Optional[int] = None):
    """
    Scan all teams in the SQLite DB and upgrade crests to HQ logos where available.
    """
    print("\n" + "=" * 60)
    print("  CREST UPGRADE: Flashscore -> High-Quality Logos")
    print("=" * 60)

    # Build logo index
    print("  [Index] Scanning logos directory...")
    index = build_logo_index()
    print(f"  [Index] Found {len(index)} team logos across {len(set(e.get('league','') for e in index.values()))} leagues")

    if not index:
        print("  [!] No logos found. Nothing to upgrade.")
        return

    # Connect to DB
    if not os.path.exists(DB_PATH):
        print(f"  [!] Database not found: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Get all teams
    query = "SELECT id, name, crest, country_code FROM teams"
    if limit:
        query += f" LIMIT {limit}"
    teams = conn.execute(query).fetchall()
    print(f"  [Teams] {len(teams)} teams in database")

    upgraded = 0
    matched = 0
    already_hq = 0

    for team in teams:
        team_name = team["name"]
        current_crest = team["crest"] or ""

        # Skip if already using HQ logo
        if "football-logos.cc" in current_crest or "Modules/Assets/logos" in current_crest.replace("\\", "/"):
            already_hq += 1
            continue

        # Try to match
        hq_path = match_team_to_logo(team_name, index)
        if hq_path:
            matched += 1
            conn.execute(
                "UPDATE teams SET crest = ?, hq_crest = 1 WHERE id = ?",
                (hq_path, team["id"])
            )
            upgraded += 1

    conn.commit()

    print(f"\n  [Results]")
    print(f"    Matched:     {matched}")
    print(f"    Upgraded:    {upgraded}")
    print(f"    Already HQ:  {already_hq}")
    print(f"    Unmatched:   {len(teams) - matched - already_hq}")
    print("=" * 60)

    # Show unmatched teams for debugging
    if len(teams) - matched - already_hq > 0:
        unmatched = []
        for team in teams:
            current_crest = team["crest"] or ""
            if "football-logos.cc" in current_crest or "Modules/Assets/logos" in current_crest.replace("\\", "/"):
                continue
            if not match_team_to_logo(team["name"], index):
                unmatched.append(team["name"])
        if unmatched:
            print(f"\n  [Unmatched Teams] ({len(unmatched)}):")
            for t in unmatched[:20]:
                print(f"    - {t}")
            if len(unmatched) > 20:
                print(f"    ... and {len(unmatched) - 20} more")

    conn.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Upgrade team crests to high-quality logos")
    parser.add_argument("--limit", type=int, help="Limit teams to process")
    args = parser.parse_args()
    upgrade_all_crests(limit=args.limit)
