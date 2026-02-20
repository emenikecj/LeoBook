# search_dict.py: search_dict.py: Module for Core — System.
# Part of LeoBook Core — System
#
# Functions: build_search_dict(), token_sort_ratio(), fuzzy_search()

from supabase import create_client
from Levenshtein import distance, ratio
import os, re, csv
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))

_search_cache = None

def build_search_dict(force=False):
    global _search_cache
    if _search_cache is not None and not force:
        return _search_cache
    cache = defaultdict(list)
    
    try:
        # Paging for large datasets (Supabase limit is 1000)
        # Teams
        page_size = 1000
        offset = 0
        while True:
            resp = supabase.table("teams").select("id,team_name,search_terms").range(offset, offset + page_size - 1).execute()
            teams = resp.data
            if not teams: break
            for t in teams:
                for term in t.get("search_terms", []):
                    cache[term.lower()].append({"id": t["id"], "type": "team", "name": t["team_name"]})
            if len(teams) < page_size: break
            offset += page_size

        # Region Leagues
        offset = 0
        while True:
            resp = supabase.table("region_league").select("rl_id,league,search_terms").range(offset, offset + page_size - 1).execute()
            leagues = resp.data
            if not leagues: break
            for l in leagues:
                for term in l.get("search_terms", []):
                    cache[term.lower()].append({"id": l["rl_id"], "type": "league", "name": l["league"]})
            if len(leagues) < page_size: break
            offset += page_size
    except Exception as e:
        print(f"Supabase connection failed ({e}), attempting local CSV fallback...")
        # Fallback to local Data/Store CSVs
        teams_csv = os.path.join("Data", "Store", "teams.csv")
        leagues_csv = os.path.join("Data", "Store", "region_league.csv")
        
        if os.path.exists(teams_csv):
            with open(teams_csv, mode='r', encoding='utf-8') as f:
                for row in csv.DictReader(f):
                    terms = json.loads(row.get("search_terms", "[]"))
                    for term in terms:
                        cache[term.lower()].append({"id": row["team_id"], "type": "team", "name": row["team_name"]})
        
        if os.path.exists(leagues_csv):
            with open(leagues_csv, mode='r', encoding='utf-8') as f:
                for row in csv.DictReader(f):
                    terms = json.loads(row.get("search_terms", "[]"))
                    for term in terms:
                        cache[term.lower()].append({"id": row["rl_id"], "type": "league", "name": row["league"]})
                        
    _search_cache = cache
    return cache

def token_sort_ratio(s1, s2):
    """Sorts words in strings alphabetically then compares them."""
    t1 = " ".join(sorted(s1.split()))
    t2 = " ".join(sorted(s2.split()))
    return ratio(t1, t2)

def fuzzy_search(query: str, top_k: int = 5):
    if not query:
        return []
    cache = build_search_dict()
    q = re.sub(r'[^a-z0-9\s]', '', query.lower().strip())
    
    # Adaptive threshold based on query length
    if len(q) < 4:
        min_threshold = 0.9
    elif len(q) < 10:
        min_threshold = 0.8
    else:
        min_threshold = 0.7

    results = []
    for term, items in cache.items():
        # Hybrid matching: standard ratio + token sort ratio
        std_score = ratio(q, term)
        sort_score = token_sort_ratio(q, term)
        
        # Take the better of the two
        score = max(std_score, sort_score)
        
        if score >= min_threshold:
            for item in items:
                results.append({**item, "score": score})
    
    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)
    
    seen = set()
    unique = []
    for r in results:
        key = (r["type"], r["id"])
        if key not in seen:
            seen.add(key)
            unique.append(r)
        if len(unique) >= top_k:
            break
    return unique
