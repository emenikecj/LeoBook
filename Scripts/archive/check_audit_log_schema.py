import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from Data.Access.supabase_client import get_supabase_client

async def check_audit_log_constraints():
    supabase = get_supabase_client()
    if not supabase:
        print("[ERROR] Could not connect to Supabase.")
        return

    print("[INFO] Checking audit_log table schema info via proxy (rpc or query)...")
    
    # We can't easily query information_schema via standard Supabase client 
    # unless we have a custom RPC. Let's try to trigger the error specifically 
    # to confirm it's still there with a dummy row.
    
    dummy_row = {
        "timestamp": "1970-01-01 00:00:00",
        "event_type": "SCHEMA_CHECK",
        "description": "Checking for unique constraint on timestamp",
        "status": "check"
    }
    
    try:
        # First attempt: Insert
        print("   [1] Attempting to insert dummy row...")
        supabase.table("audit_log").insert(dummy_row).execute()
        
        # Second attempt: Upsert with same timestamp
        print("   [2] Attempting to upsert same row (should fail if unique constraint is missing)...")
        res = supabase.table("audit_log").upsert(dummy_row, on_conflict="timestamp").execute()
        print("   [SUCCESS] Upsert worked! Unique constraint exists.")
        
    except Exception as e:
        print(f"   [FAILURE] Upsert failed as expected: {e}")
        if "42P10" in str(e) or "no unique or exclusion constraint" in str(e).lower():
            print("\n[CONFIRMED] The 'audit_log' table is missing a UNIQUE constraint on the 'timestamp' column.")
            print("\nTo fix this, please run the following SQL in your Supabase SQL Editor:")
            print("----------------------------------------------------------------------")
            print("ALTER TABLE audit_log ADD CONSTRAINT audit_log_timestamp_unique UNIQUE (timestamp);")
            print("----------------------------------------------------------------------")
        else:
            print(f"   [OTHER ERROR] {e}")

if __name__ == "__main__":
    asyncio.run(check_audit_log_constraints())
