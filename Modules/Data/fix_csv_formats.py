# fix_csv_formats.py: fix_csv_formats.py: Module for Modules — Data Processing.
# Part of LeoBook Modules — Data Processing
#
# Functions: normalize_date(), fix_csvs()

import pandas as pd
import re
from pathlib import Path

# Paths
DATA_DIR = Path("Data/Store")
FILES_TO_FIX = ["schedules.csv", "predictions.csv", "fb_matches.csv"]

def normalize_date(val):
    if not isinstance(val, str) or not val:
        return val
    
    # Match DD.MM.YYYY
    match_full = re.match(r'^(\d{2})\.(\d{2})\.(\d{4})$', val)
    if match_full:
        d, m, y = match_full.groups()
        return f"{y}-{m}-{d}"
    
    # Match DD.MM.YY
    match_short = re.match(r'^(\d{2})\.(\d{2})\.(\d{2})$', val)
    if match_short:
        d, m, y_short = match_short.groups()
        return f"20{y_short}-{m}-{d}"
    
    return val

def fix_csvs():
    for filename in FILES_TO_FIX:
        path = DATA_DIR / filename
        if not path.exists():
            print(f"Skipping {filename} (not found)")
            continue
        
        print(f"Normalizing {filename}...")
        df = pd.read_csv(path, dtype=str).fillna('')
        
        date_cols = [c for c in df.columns if c in ['date', 'date_updated', 'last_extracted']]
        for col in date_cols:
            df[col] = df[col].apply(normalize_date)
        
        df.to_csv(path, index=False, encoding='utf-8')
        print(f"Fixed {filename}")

if __name__ == "__main__":
    fix_csvs()
