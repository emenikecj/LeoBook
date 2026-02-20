import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from Data.Access.supabase_client import get_supabase_client

async def clean_audit_log():
    supabase = get_supabase_client()
    if not supabase:
        print("[ERROR] No connection.")
        return

    print("[INFO] removing dummy rows (1970-01-01)...")
    try:
        # Delete the specific dummy timestamp we inserted
        res = supabase.table("audit_log").delete().eq("timestamp", "1970-01-01 00:00:00").execute()
        print(f"[SUCCESS] Deleted {len(res.data)} dummy rows.")
    except Exception as e:
        print(f"[ERROR] Failed to delete: {e}")

if __name__ == "__main__":
    asyncio.run(clean_audit_log())
