import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import logging
from Data.Access.sync_manager import TABLE_CONFIG, SyncManager, DATA_DIR
from Data.Access.db_helpers import files_and_headers
import os
from pathlib import Path

logging.basicConfig(level=logging.INFO)

async def probe_schemas():
    sync = SyncManager()
    if not sync.supabase:
        print("Supabase client not initialized.")
        return

    for table_key, config in TABLE_CONFIG.items():
        table_name = config['table']
        csv_file = config['csv']
        csv_path = str(DATA_DIR / csv_file)
        
        local_headers = set(files_and_headers.get(csv_path, []))
        local_headers.update(['last_updated'])
        
        print(f"\nChecking table: {table_name}")
        try:
            res = sync.supabase.table(table_name).select("*").limit(1).execute()
            if res.data:
                remote_cols = set(res.data[0].keys())
                print(f"  Remote columns: {sorted(list(remote_cols))}")
                missing_in_remote = local_headers - remote_cols
                # Handle dot in column name mapping
                if 'over_2.5' in missing_in_remote and 'over_2_5' in remote_cols:
                    missing_in_remote.remove('over_2.5')
                
                if missing_in_remote:
                    print(f"  [MISSING IN SUPABASE]: {missing_in_remote}")
                else:
                    print(f"  [OK] Remote schema matches local headers.")
            else:
                print(f"  [EMPTY] Table exists but has no data. Cannot probe columns via SELECT *.")
        except Exception as e:
            print(f"  [ERROR] Could not probe {table_name}: {e}")

if __name__ == '__main__':
    asyncio.run(probe_schemas())
