import csv
import os
import json
import time
import requests
import re
from collections import defaultdict
from supabase import create_client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ================================================
# Configuration
# ================================================
CSV_FILE = os.path.join("Data", "Store", "schedules.csv")
TEAMS_CSV = os.path.join("Data", "Store", "teams.csv")
REGION_LEAGUE_CSV = os.path.join("Data", "Store", "region_league.csv")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

# ───────────────────────────────────────────────
# xAI Grok API Configuration
# ───────────────────────────────────────────────
GROK_API_KEY = os.getenv("GROK_API_KEY")
GROK_API_URL = "https://api.x.ai/v1/chat/completions"
MODEL = "grok-4-1-fast-reasoning" 
HEADERS = {
    "Authorization": f"Bearer {GROK_API_KEY}",
    "Content-Type": "application/json"
}
BATCH_SIZE = 10 # Process in small batches
SLEEP_BETWEEN_BATCHES = 2 # Seconds

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY in .env")

# Initialize Supabase
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def normalize_for_search(name: str) -> str:
    """Standard normalization for search term generation."""
    if not name: return ""
    return re.sub(r'[^a-z0-9\s]', '', name.lower().strip())

def query_grok_for_metadata_with_retry(items, item_type="team", retries=3):
    """
    Wrapper for query_grok_for_metadata with retry logic.
    """
    for attempt in range(retries):
        try:
            return query_grok_for_metadata(items, item_type)
        except Exception as e:
            print(f"  [Warning] Grok API attempt {attempt+1}/{retries} failed: {e}")
            time.sleep(5 * (attempt + 1)) # Exponential backoff
    print(f"  [Error] Grok API failed after {retries} attempts.")
    return []

def query_grok_for_metadata(items, item_type="team"):
    """
    Sends a batch of team/league names to Grok and asks for structured metadata.
    Returns list of dicts with enriched info.
    """
    if not items:
        return []
    
    items_list = "\n".join([f"- {name}" for name in items])
    if item_type == "team":
        prompt = f"""You are a football/soccer database expert.
Here is a list of team names extracted from match schedules:
{items_list}
For EACH team, return accurate, canonical metadata in this exact JSON structure.
Use the most commonly accepted official name today.
Include alternative / historical / sponsor names when relevant.
Do NOT invent information — if uncertain, use "unknown".
Output ONLY valid JSON array of objects with these keys:
[
  {{
    "input_name": "exact name from list",
    "official_name": "most official / current name",
    "other_names": ["array", "of", "known", "aliases", "nicknames"],
    "abbreviations": ["short codes", "common abbr"],
    "country": "ISO 3166-1 alpha-2 or full country name",
    "city": "main city/base (if known)",
    "stadium": "home stadium name or null",
    "league": "primary current league (short name)",
    "founded": year or null,
    "crest_url": "official or reliable crest image URL or null",
    "wikipedia_url": "best Wikipedia page or null"
  }}
]
Return ONLY the JSON array — no explanations, no markdown.
"""
    else: # league
        prompt = f"""You are a football/soccer database expert.
Here is a list of league/competition identifiers:
{items_list}
For EACH one, return accurate, canonical metadata in this exact JSON structure.
Use the current official name (including title sponsor if it's the primary branding).
Include alternative / previous / short names.
Output ONLY valid JSON array of objects with these keys:
[
  {{
    "input_name": "exact name from list",
    "official_name": "current official name",
    "other_names": ["previous names", "short names", "sponsor variants"],
    "abbreviations": ["common short codes"],
    "country": "country or 'International' / 'Continental'",
    "level": "top-tier / second / etc or null",
    "season_format": "Apertura/Clausura, single table, etc or null",
    "logo_url": "official or reliable logo URL or null",
    "wikipedia_url": "best Wikipedia page or null"
  }}
]
Return ONLY the JSON array — no explanations, no markdown.
"""
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 4096
    }
    try:
        resp = requests.post(GROK_API_URL, headers=HEADERS, json=payload, timeout=60)
        resp.raise_for_status()
    except Exception as e:
        print(f"Grok API error: {e}")
        try:
            print(f"Response: {resp.text}")
        except:
            pass
        return []
        
    content = resp.json()["choices"][0]["message"]["content"].strip()
    # Clean markdown if present
    if content.startswith("```json"):
        content = content[7:-3].strip()
    elif content.startswith("```"):
        content = content[3:-3].strip()
        
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        print("Warning: Grok response was not valid JSON:\n", content[:300], "...")
        return []

def update_csv_file(file_path, data_map, key_field, headers):
    """
    Updates a local CSV file with enriched data.
    data_map: dict of key -> dict of fields to update
    """
    if not os.path.exists(file_path):
        print(f"Warning: CSV file {file_path} not found. Skipping update.")
        return

    temp_file = file_path + ".tmp"
    updated_count = 0
    new_count = 0
    seen_keys = set()
    
    with open(file_path, mode='r', encoding='utf-8', newline='') as infile, \
         open(temp_file, mode='w', encoding='utf-8', newline='') as outfile:
        
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames
        
        # Ensure new columns exist in header
        for h in headers:
            if h not in fieldnames:
                fieldnames.append(h)
        
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for row in reader:
            key = row.get(key_field)
            if key and key in data_map:
                update_data = data_map[key]
                for k, v in update_data.items():
                    if k in fieldnames:
                         # Handle list serialization for CSV if needed (e.g. JSON string)
                        if isinstance(v, (list, dict)):
                            row[k] = json.dumps(v)
                        else:
                            row[k] = v
                updated_count += 1
                seen_keys.add(key)
            writer.writerow(row)
        
        # Append new rows
        for key, data in data_map.items():
            if key not in seen_keys:
                new_row = {k: '' for k in fieldnames} # Default empty
                # Fill known fields
                for k, v in data.items():
                    if k in fieldnames:
                        if isinstance(v, (list, dict)):
                            new_row[k] = json.dumps(v)
                        else:
                            new_row[k] = v
                
                # Ensure key field is set
                if key_field not in new_row or not new_row[key_field]:
                     new_row[key_field] = key

                writer.writerow(new_row)
                new_count += 1
            
    os.replace(temp_file, file_path)
    print(f"Updated {updated_count} rows and added {new_count} new rows in {file_path}")

def main():
    if not os.path.exists(CSV_FILE):
        print(f"Error: {CSV_FILE} not found.")
        return

    leagues_raw = set()
    teams_raw = defaultdict(lambda: {"id": None, "names": set()})

    print(f"Reading {CSV_FILE} and collecting unique teams/leagues...")
    with open(CSV_FILE, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rl = (row.get("region_league") or "Unknown").strip()
            leagues_raw.add(rl)
            for prefix in ["home_", "away_"]:
                tname = (row.get(prefix + "team") or "").strip()
                tid = (row.get(prefix + "team_id") or "").strip()
                if not tname or not tid:
                    continue
                teams_raw[tid]["id"] = tid
                teams_raw[tid]["names"].add(tname)

    print(f"Found {len(leagues_raw)} unique league keys")
    print(f"Found {len(teams_raw)} unique teams (by ID)")

    # Prepared Update Maps for CSVs
    league_updates = {}
    team_updates = {}

    # Load existing region_league IDs for matching
    existing_rl_ids = set()
    if os.path.exists(REGION_LEAGUE_CSV):
        with open(REGION_LEAGUE_CSV, mode='r', encoding='utf-8') as f:
            r = csv.DictReader(f)
            for row in r:
                if row.get("rl_id"):
                    existing_rl_ids.add(row["rl_id"])
    
    def find_best_rl_id(name):
        # 1. Exact match
        if name in existing_rl_ids: return name
        
        # 2. Slugify match
        slug = re.sub(r'[\s]+', '-', re.sub(r'[^a-z0-9\s-]', '', name.lower().strip()))
        if slug in existing_rl_ids: return slug

        # 3. Try to match just the league part if "Region - League" format
        if " - " in name:
            part_slug = re.sub(r'[\s]+', '-', re.sub(r'[^a-z0-9\s-]', '', name.split(" - ")[-1].lower().strip()))
            if part_slug in existing_rl_ids: return part_slug
            
        return name # Fallback to input name

    # ───────────────────────────────────────────────
    # Enrich and Upsert Leagues
    # ───────────────────────────────────────────────
    league_list = list(leagues_raw)
    print("\nEnriching and syncing leagues...")
    for i in range(0, len(league_list), BATCH_SIZE):
        batch = league_list[i:i + BATCH_SIZE]
        print(f" Processing league batch {i//BATCH_SIZE + 1} ({len(batch)} items)")
        results = query_grok_for_metadata_with_retry(batch, item_type="league")
        print(results)
        for item in results:
            input_name = item.get("input_name")
            official_name = item.get("official_name") or input_name
            
            # Determine correct ID for CSV sync
            rl_id_key = find_best_rl_id(input_name)

            # Build search terms
            search_terms = {normalize_for_search(input_name), normalize_for_search(official_name)}
            for n in item.get("other_names", []):
                search_terms.add(normalize_for_search(n))
            for a in item.get("abbreviations", []):
                search_terms.add(normalize_for_search(a))
            
            # Add misspellings/aliases
            for term in list(search_terms):
                search_terms.add(term.replace("league", "lge"))
                search_terms.add(term.replace("cup", "cp"))

            upsert_data = {
                "league": official_name, # map to league
                "other_names": item.get("other_names", []),
                "abbreviations": item.get("abbreviations", []),
                "search_terms": list(filter(None, search_terms)),
                "country": item.get("country"),
                "logo_url": item.get("logo_url")
            }
            
            # Prepare CSV update data using the matched ID
            league_updates[rl_id_key] = upsert_data

            # Upsert using region_league/input_name logic
            try:
                # Primary key for region_league is rl_id
                supabase.table("region_league").upsert(
                    {**upsert_data, "rl_id": rl_id_key}
                ).execute()
            except Exception as e:
                # Ignore empty response error (PGRST204)
                if "JSONDecodeError" in str(e) or "204" in str(e):
                    pass
                else:
                    print(f"  [Error] Upsert failed for region_league {input_name}: {e}")
                
                
        time.sleep(SLEEP_BETWEEN_BATCHES) # Wait between batches

        # INCREMENTAL UPDATE: Update Region League CSV after each batch
        if league_updates:
            print(f" Syncing {len(league_updates)} league updates to local CSV...")
            update_csv_file(REGION_LEAGUE_CSV, league_updates, "rl_id", ["league", "other_names", "abbreviations", "search_terms", "country", "logo_url"])
            league_updates.clear() # Clear specific batch updates after writing

    # ───────────────────────────────────────────────
    # Enrich and Upsert Teams
    # ───────────────────────────────────────────────
    team_ids = list(teams_raw.keys())
    print("\nEnriching and syncing teams...")
    for i in range(0, len(team_ids), BATCH_SIZE):
        batch_ids = team_ids[i:i + BATCH_SIZE]
        batch_names = [list(teams_raw[tid]["names"])[0] for tid in batch_ids]
        print(f" Processing team batch {i//BATCH_SIZE + 1} ({len(batch_ids)} teams)")
        results = query_grok_for_metadata_with_retry(batch_names, item_type="team")
        
        for idx, item in enumerate(results):
            if idx >= len(batch_ids): break
            tid = batch_ids[idx]
            input_names = teams_raw[tid]["names"]
            official_name = item.get("official_name") or list(input_names)[0]

            # Build search terms
            search_terms = {normalize_for_search(official_name)}
            for n in input_names:
                search_terms.add(normalize_for_search(n))
            for n in item.get("other_names", []):
                search_terms.add(normalize_for_search(n))
            for a in item.get("abbreviations", []):
                search_terms.add(normalize_for_search(a))

            # Add misspellings/aliases
            for term in list(search_terms):
                search_terms.add(term.replace("united", "utd"))
                search_terms.add(term.replace("city", "fc"))

            upsert_data = {
                "team_id": tid, # use team_id as per schema
                "team_name": official_name, # map to team_name
                "other_names": item.get("other_names", []),
                "abbreviations": item.get("abbreviations", []),
                "search_terms": list(filter(None, search_terms)),
                "country": item.get("country"),
                "city": item.get("city"),
                "stadium": item.get("stadium"),
                "team_crest": item.get("crest_url") # column is team_crest in schema
            }
            
            # Prepare CSV update data
            team_updates[tid] = upsert_data

            try:
                supabase.table("teams").upsert(upsert_data).execute()
            except Exception as e:
                # Handle missing column error (e.g. stadium) -> retry without stadium
                if "stadium" in str(e) or "column" in str(e):
                    print(f"  [Warning] Upsert failed due to schema mismatch (likely missing 'stadium'). Retrying without stadium...")
                    try:
                        data_no_stadium = upsert_data.copy()
                        data_no_stadium.pop("stadium", None)
                        supabase.table("teams").upsert(data_no_stadium).execute()
                    except Exception as e2:
                        print(f"  [Error] Retry failed for team {tid}: {e2}")
                # Ignore empty response error
                elif "JSONDecodeError" in str(e) or "204" in str(e):
                    pass
                else:
                    print(f"  [Error] Upsert failed for team {tid}: {e}")
                
        time.sleep(SLEEP_BETWEEN_BATCHES) # Wait between batches

        # INCREMENTAL UPDATE: Update Teams CSV after each batch
        if team_updates:
            print(f" Syncing {len(team_updates)} team updates to local CSV...")
            update_csv_file(TEAMS_CSV, team_updates, "team_id", ["team_name", "other_names", "abbreviations", "search_terms", "country", "city", "stadium", "team_crest"])
            team_updates.clear() # Clear specific batch updates after writing

    print("\nSearch dictionary built and local CSVs/Supabase synced!")

if __name__ == "__main__":
    main()
