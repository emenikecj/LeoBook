from supabase import create_client
from Levenshtein import distance
import os, re
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
    # Teams
    teams = supabase.table("teams").select("id,team_name,search_terms").execute().data
    for t in teams:
        for term in t.get("search_terms", []):
            cache[term.lower()].append({"id": t["id"], "type": "team", "name": t["team_name"]})
    # Region Leagues
    leagues = supabase.table("region_league").select("rl_id,league,search_terms").execute().data
    for l in leagues:
        for term in l.get("search_terms", []):
            cache[term.lower()].append({"id": l["rl_id"], "type": "league", "name": l["league"]})
    _search_cache = cache
    return cache

def fuzzy_search(query: str, top_k: int = 5, max_dist: int = 2):
    if not query:
        return []
    cache = build_search_dict()
    q = re.sub(r'[^a-z0-9\s]', '', query.lower().strip())
    results = []
    for term, items in cache.items():
        dist = distance(q, term)
        if dist <= max_dist:
            for item in items:
                results.append({**item, "distance": dist})
    results.sort(key=lambda x: x["distance"])
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
