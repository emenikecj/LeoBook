import csv
import os
import json
import time
import requests
import re
import unicodedata
import uuid
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
    """Standard normalization for search term generation (NFKD for accents)."""
    if not name: return ""
    # Normalize unicode characters to decompose accents
    nfkd_form = unicodedata.normalize('NFKD', name)
    # Filter out non-ASCII characters (accents)
    only_ascii = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    # Remove non-alphanumeric and lower
    return re.sub(r'[^a-z0-9\s]', '', only_ascii.lower().strip())

def generate_deterministic_id(name: str, context: str = "") -> str:
    """Generates a deterministic ID using UUIDv5 as a fallback for slugs."""
    namespace = uuid.NAMESPACE_DNS
    unique_string = f"leobook-{context}-{normalize_for_search(name)}"
    return str(uuid.uuid5(namespace, unique_string))

def extract_json_with_salvage(text: str) -> list:
    """
    Attempts to extract JSON from text even if malformed or truncated.
    Returns a list of salvaged objects.
    """
    if not text: return []
    
    # 1. Try standard regex for JSON block
    match = re.search(r'\[\s*\{.*\}\s*\]', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except:
            pass
            
    # 2. Salvage individual objects if the array is broken
    objects = []
    # Find potential JSON objects: {...}
    potential_objects = re.findall(r'\{[^{}]*\}', text)
    for obj_str in potential_objects:
        try:
            obj = json.loads(obj_str)
            if isinstance(obj, dict) and "input_name" in obj:
                objects.append(obj)
        except:
            continue
    
    # 3. If still empty, try to fix common truncation issues (missing closing bracket)
    if not objects and "[" in text:
        try:
            # Append missing brackets/braces to see if it parses
            salvaged = text.strip()
            if not salvaged.endswith("]"):
                if not salvaged.endswith("}"): salvaged += "}"
                salvaged += "]"
            return json.loads(salvaged)
        except:
            pass
            
    return objects

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
    """
    Tries to find an existing league ID using exact match or slug matching.
    Returns (rl_id, is_new)
    """
    # 1. Exact Name Match
    for rl_id, data in existing_leagues_map.items():
        if data.get('league') == league_name:
            return rl_id, False
            
    # 2. Slug Match (Name + Country for uniqueness)
    slug_base = normalize_for_search(league_name).replace(" ", "-")
    country_slug = normalize_for_search(country).replace(" ", "-") if country else "intl"
    full_slug = f"{country_slug}-{slug_base}"
    
    if full_slug in existing_leagues_map:
        return full_slug, False
        
    if slug_base in existing_leagues_map:
         return slug_base, False

    # 3. UUID Fallback if names are extremely common or context is missing
    det_id = generate_deterministic_id(league_name, context=country or "intl")
    if det_id in existing_leagues_map:
        return det_id, False

    # 4. Create New ID (prefer full slug if possible, else UUID)
    return full_slug if len(full_slug) < 100 else det_id, True

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
    
    # Salvage data from potential malformed JSON
    data = extract_json_with_salvage(content)
    if not data:
        print("Warning: Grok response yielded no valid JSON:\n", content[:300], "...")
        return []

    # Basic key validation
    validated_data = []
    for item in data:
        if isinstance(item, dict) and "input_name" in item:
            validated_data.append(item)
        else:
            print(f"  [Warning] Skipping irrelevant Grok item: {item}")
    return validated_data

def batch_upsert(table_name: str, data: list, chunk_size: int = 1000):
    """Upserts data to Supabase in chunks to avoid payload limits."""
    for i in range(0, len(data), chunk_size):
        chunk = data[i:i + chunk_size]
        try:
            supabase.table(table_name).upsert(chunk).execute()
        except Exception as e:
            print(f"  [Error] Batch upsert to {table_name} failed (chunk starting at {i}): {e}")
            # Individual fallback if batch fails
            if len(chunk) > 1:
                print("  [Info] Retrying chunk items individually...")
                for item in chunk:
                    try:
                        supabase.table(table_name).upsert(item).execute()
                    except Exception as e2:
                        print(f"  [Error] Individual upsert failed: {e2}")

def update_csv_file(file_path, data_map, key_field, headers):

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

def find_best_match_league(input_name: str, country: str, existing_leagues: dict):
    """
    Match an input league name against existing league rows.
    Returns (rl_id, is_new).
    """
    norm_input = normalize_for_search(input_name)
    # Strip round/stage suffixes for matching: "TURKEY - 1. LIG - ROUND 22" → "turkey 1 lig"
    norm_input_base = re.sub(r'\s*-?\s*(round|matchday|playoffs?|apertura|clausura|1/\d+-finals?|group\s*\w)\s*.*$', '', norm_input, flags=re.IGNORECASE).strip()

    best_id = None
    best_score = 0

    for rl_id, row in existing_leagues.items():
        existing_name = normalize_for_search(row.get("league", ""))
        existing_country = (row.get("country") or "").strip().lower()

        # Country must match if both are present
        if country and existing_country and country.strip().lower() != existing_country:
            continue

        # Exact match
        if norm_input_base == existing_name:
            return rl_id, False

        # Substring containment score
        if norm_input_base and existing_name:
            if norm_input_base in existing_name or existing_name in norm_input_base:
                score = len(existing_name)
                if score > best_score:
                    best_score = score
                    best_id = rl_id

    if best_id:
        return best_id, False

    # No match — generate deterministic ID
    new_id = generate_deterministic_id(input_name, country or "")
    return new_id, True


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

    # ───────────────────────────────────────────────
    # TWO-PASS ENRICHMENT STRATEGY
    #   Pass 1: Items with NO search_terms  (empty → enrich)
    #   Pass 2: Items WITH search_terms but MISSING critical fields (incomplete → re-enrich)
    # ───────────────────────────────────────────────
    fully_enriched_team_ids = set()   # have search_terms AND all critical fields
    incomplete_team_ids = set()       # have search_terms but missing critical fields
    TEAM_CRITICAL_FIELDS = ['country', 'city', 'stadium', 'team_crest']
    if os.path.exists(TEAMS_CSV):
        with open(TEAMS_CSV, mode='r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                st = row.get('search_terms', '').strip()
                tid = row.get('team_id', '').strip()
                if not tid:
                    continue
                if st and st != '[]':
                    # Has search_terms — check if critical fields are filled
                    missing = [fld for fld in TEAM_CRITICAL_FIELDS
                               if not row.get(fld, '').strip()]
                    if missing:
                        incomplete_team_ids.add(tid)
                    else:
                        fully_enriched_team_ids.add(tid)

    fully_enriched_league_keys = set()
    incomplete_league_keys = set()
    LEAGUE_CRITICAL_FIELDS = ['country', 'logo_url']
    if os.path.exists(REGION_LEAGUE_CSV):
        with open(REGION_LEAGUE_CSV, mode='r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                st = row.get('search_terms', '').strip()
                lkey = row.get('league', '').strip()
                if not lkey:
                    continue
                if st and st != '[]':
                    missing = [fld for fld in LEAGUE_CRITICAL_FIELDS
                               if not row.get(fld, '').strip()]
                    if missing:
                        incomplete_league_keys.add(lkey)
                    else:
                        fully_enriched_league_keys.add(lkey)

    print(f"\n[PASS 1] Teams:   {len(teams_raw) - len(fully_enriched_team_ids) - len(incomplete_team_ids)} empty → enrich")
    print(f"[PASS 2] Teams:   {len(incomplete_team_ids)} incomplete → re-enrich")
    print(f"[SKIP]   Teams:   {len(fully_enriched_team_ids)} fully enriched")
    print(f"[PASS 1] Leagues: {len(leagues_raw) - len(fully_enriched_league_keys) - len(incomplete_league_keys)} empty → enrich")
    print(f"[PASS 2] Leagues: {len(incomplete_league_keys)} incomplete → re-enrich")
    print(f"[SKIP]   Leagues: {len(fully_enriched_league_keys)} fully enriched")

    # Prepared Update Maps for CSVs
    league_updates = {}
    team_updates = {}

    # Load existing region_league data for matching
    existing_leagues = {}
    if os.path.exists(REGION_LEAGUE_CSV):
        with open(REGION_LEAGUE_CSV, mode='r', encoding='utf-8') as f:
            r = csv.DictReader(f)
            for row in r:
                if row.get("rl_id"):
                    existing_leagues[row["rl_id"]] = row

    # ───────────────────────────────────────────────
    # PASS 1: Enrich leagues with NO search_terms
    # ───────────────────────────────────────────────
    league_list_all = list(leagues_raw)
    league_list_pass1 = [l for l in league_list_all if l not in fully_enriched_league_keys and l not in incomplete_league_keys]
    league_list_pass2 = [l for l in league_list_all if l in incomplete_league_keys]
    print(f"\n── PASS 1: Enriching {len(league_list_pass1)} empty leagues ──")
    for league_list, pass_name in [(league_list_pass1, "PASS 1"), (league_list_pass2, "PASS 2")]:
      if not league_list:
        print(f"  [{pass_name}] No leagues to process, skipping.")
        continue
      print(f"  [{pass_name}] Processing {len(league_list)} leagues...")
      for i in range(0, len(league_list), BATCH_SIZE):
        batch = league_list[i:i + BATCH_SIZE]
        print(f" Processing league batch {i//BATCH_SIZE + 1} ({len(batch)} items)")
        results = query_grok_for_metadata_with_retry(batch, item_type="league")
        print(results)
        for item in results:
            input_name = item.get("input_name")
            official_name = item.get("official_name") or input_name
            country = item.get("country")
            
            # Determine correct ID for CSV sync (using country context)
            rl_id_key, is_new = find_best_match_league(input_name, country, existing_leagues)

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

            # Prepare for batch upsert
            league_updates[rl_id_key] = {**upsert_data, "rl_id": rl_id_key}

        # Batched Upsert to Supabase
        if league_updates:
            print(f"  [Supabase] Batch upserting {len(league_updates)} leagues...")
            batch_upsert("region_league", list(league_updates.values()))

        time.sleep(SLEEP_BETWEEN_BATCHES) # Wait between batches

        # INCREMENTAL UPDATE: Update Region League CSV after each batch
        if league_updates:
            print(f" Syncing {len(league_updates)} league updates to local CSV...")
            update_csv_file(REGION_LEAGUE_CSV, league_updates, "rl_id", ["league", "other_names", "abbreviations", "search_terms", "country", "logo_url"])
            league_updates.clear() # Clear specific batch updates after writing

    # ───────────────────────────────────────────────
    # PASS 1 + PASS 2: Enrich Teams
    # ───────────────────────────────────────────────
    team_ids_all = list(teams_raw.keys())
    team_ids_pass1 = [tid for tid in team_ids_all if tid not in fully_enriched_team_ids and tid not in incomplete_team_ids]
    team_ids_pass2 = [tid for tid in team_ids_all if tid in incomplete_team_ids]
    print(f"\n── PASS 1: Enriching {len(team_ids_pass1)} empty teams ──")
    print(f"── PASS 2: Re-enriching {len(team_ids_pass2)} incomplete teams ──")
    for team_ids, pass_name in [(team_ids_pass1, "PASS 1"), (team_ids_pass2, "PASS 2")]:
      if not team_ids:
        print(f"  [{pass_name}] No teams to process, skipping.")
        continue
      print(f"  [{pass_name}] Processing {len(team_ids)} teams...")
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

              # Prepare for batch upsert
              team_updates[tid] = upsert_data

          # Batched Upsert to Supabase
          if team_updates:
              print(f"  [Supabase] Batch upserting {len(team_updates)} teams...")
              batch_upsert("teams", list(team_updates.values()))
                
          time.sleep(SLEEP_BETWEEN_BATCHES) # Wait between batches

          # INCREMENTAL UPDATE: Update Teams CSV after each batch
          if team_updates:
              print(f" Syncing {len(team_updates)} team updates to local CSV...")
              update_csv_file(TEAMS_CSV, team_updates, "team_id", ["team_name", "other_names", "abbreviations", "search_terms", "country", "city", "stadium", "team_crest"])
              team_updates.clear() # Clear specific batch updates after writing

    print("\nSearch dictionary built and local CSVs/Supabase synced!")

if __name__ == "__main__":
    main()
