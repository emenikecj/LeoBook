import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import logging
from Data.Access.sync_manager import SyncManager

logging.basicConfig(level=logging.INFO)

async def test_sync():
    sync = SyncManager()
    if not sync.supabase:
        print("Supabase client not initialized.")
        return

    print("\n[VERIFICATION] Starting synchronization test...")
    try:
        # Sync schedules
        await sync._sync_table('schedules', {'csv': 'schedules.csv', 'table': 'schedules', 'key': 'fixture_id'})
        print("[OK] Schedules synchronized.")

        # Sync predictions
        await sync._sync_table('predictions', {'csv': 'predictions.csv', 'table': 'predictions', 'key': 'fixture_id'})
        print("[OK] Predictions synchronized.")
        
        print("\n[SUCCESS] Supabase synchronization verified with the new schema.")
    except Exception as e:
        print(f"\n[ERROR] Synchronization failed: {e}")

if __name__ == '__main__':
    asyncio.run(test_sync())
