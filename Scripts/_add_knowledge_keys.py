"""Add new selector keys to knowledge.json for the selector migration."""
import json

KNOWLEDGE_PATH = "Config/knowledge.json"

with open(KNOWLEDGE_PATH, "r", encoding="utf-8") as f:
    k = json.load(f)

# --- fs_home_page keys ---
k["fs_home_page"]["expand_show_more_button"] = (
    '.wclIcon__leagueShowMoreCont .wcl-trigger_CGiIV[data-state="delayed-open"] '
    'button.wcl-accordion_7Fi80'
)
k["fs_home_page"]["all_tab"] = '.filters__tab[data-analytics-alias="summary"]'
k["fs_home_page"]["all_tab_fallback"] = ".filters__tab"
k["fs_home_page"]["cookie_accept_onetrust"] = "#onetrust-accept-btn-handler"

# --- fb_match_page keys ---
k["fb_match_page"]["bet_insights_header"] = "div.srct-widget-header_custom"
k["fb_match_page"]["bet_insights_arrow"] = "div.srct-widget-header_custom-arrow"
k["fb_match_page"]["live_indicator"] = (
    "div.live-in-play-icon, [data-testid='wcl-icon-live'], .live-tag, span.live-in-play-icon"
)
k["fb_match_page"]["app_iframe"] = "#app"

with open(KNOWLEDGE_PATH, "w", encoding="utf-8") as f:
    json.dump(k, f, indent=2, ensure_ascii=False)

print("[OK] Added 8 new keys to knowledge.json")
for ctx in ["fs_home_page", "fb_match_page"]:
    print(f"  {ctx}: {len(k[ctx])} total keys")
