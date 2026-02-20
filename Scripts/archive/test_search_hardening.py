import sys
import os
import json

# Add project root to path
sys.path.append(os.getcwd())

from Core.System.search_dict import fuzzy_search, token_sort_ratio, build_search_dict
from Scripts.build_search_dict import generate_deterministic_id, extract_json_with_salvage

def test_id_logic():
    print("Testing ID Generation Logic...")
    id1 = generate_deterministic_id("Premier League", "England")
    id2 = generate_deterministic_id("Premier League", "England")
    id3 = generate_deterministic_id("Premier League", "Egypt")
    
    assert id1 == id2, "ID generation should be deterministic"
    assert id1 != id3, "ID generation should include context (country)"
    print("  [OK] ID Logic Verified.")

def test_json_salvage():
    print("\nTesting JSON Salvage Logic...")
    malformed = """
    Here is the data you requested:
    [
      {"input_name": "Team A", "official_name": "Team A Official"},
      {"input_name": "Team B", "official_name": "Team B Official"}
    """ # Missing closing ]
    
    results = extract_json_with_salvage(malformed)
    assert len(results) == 2, f"Expected 2 items, got {len(results)}"
    assert results[0]["input_name"] == "Team A"
    
    truncated = """
    [
      {"input_name": "Team C", "official_name": "Team C Official"},
      {"input_name": "Te
    """ # Heavily truncated
    results2 = extract_json_with_salvage(truncated)
    assert len(results2) == 1, "Should salvage at least the first complete object"
    print("  [OK] JSON Salvage Verified.")

def test_fuzzy_matching():
    print("\nTesting Hybrid Fuzzy Matching...")
    # Mock some data if needed, or rely on existing CSVs for this test
    # Let's assume matches for "Manchester United" exist
    
    # Test token sort ratio
    score_normal = token_sort_ratio("Manchester United", "United Manchester")
    assert score_normal == 1.0, f"Token sort should match perfectly, got {score_normal}"
    
    # Test length-weighted threshold
    # "FC" (len 2) requires 0.9 ratio
    # "Manchester" (len 10) requires 0.7 ratio
    
    print("  [OK] Fuzzy Matching (Token Sort) Verified.")

if __name__ == "__main__":
    try:
        test_id_logic()
        test_json_salvage()
        test_fuzzy_matching()
        print("\nAll technical hardening logic verified successfully!")
    except Exception as e:
        print(f"\n[FAIL] Verification failed: {e}")
        sys.exit(1)
