import pandas as pd
import os

SCHEDULES_CSV = 'Data/Store/schedules.csv'

def migrate_status():
    if not os.path.exists(SCHEDULES_CSV):
        print(f"File not found: {SCHEDULES_CSV}")
        return

    print(f"Reading {SCHEDULES_CSV}...")
    df = pd.read_csv(SCHEDULES_CSV, dtype=str).fillna('')
    
    if 'status' not in df.columns:
        print("No 'status' column found. Migration may have already run.")
        return

    # Check for match_status column or create it
    if 'match_status' not in df.columns:
        df['match_status'] = ''

    # Migrate: if match_status is empty and status is not, move it
    mask = (df['match_status'] == '') & (df['status'] != '')
    moved_count = mask.sum()
    df.loc[mask, 'match_status'] = df.loc[mask, 'status']
    
    # Also standardize existing match_status from status if they differ but match_status is generic
    # (e.g. match_status='scheduled' vs status='POSTPONED')
    mask_fix = (df['match_status'].str.lower() == 'scheduled') & (df['status'].str.lower() != 'scheduled') & (df['status'] != '')
    df.loc[mask_fix, 'match_status'] = df.loc[mask_fix, 'status']
    moved_count += mask_fix.sum()
    
    print(f"Migrated {moved_count} status values to match_status.")
    
    # Drop status column
    df.drop(columns=['status'], inplace=True)
    print("Dropped 'status' column.")
    
    # Save back
    df.to_csv(SCHEDULES_CSV, index=False)
    print(f"Successfully saved {SCHEDULES_CSV}")

if __name__ == "__main__":
    migrate_status()
