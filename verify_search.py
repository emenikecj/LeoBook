from Core.System.search_dict import fuzzy_search
import time

print("Testing fuzzy search...")
results_utd = fuzzy_search("man utd")
print(f"man utd: {results_utd}")

results_pl = fuzzy_search("premier league")
print(f"premier league: {results_pl}")

results_barca = fuzzy_search("barcelona")
print(f"barcelona: {results_barca}")
