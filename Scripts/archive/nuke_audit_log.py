
import asyncio
from Data.Access.supabase_client import get_supabase_client

async def nuke_remote_audit_log():
    sb = get_supabase_client()
    if not sb:
        print("Could not get Supabase client.")
        return

    print("Clearing remote audit_log table...")
    try:
        # Delete all rows
        res = sb.table("audit_log").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
        print(f"Purged remote audit_log. Response: {res}")
    except Exception as e:
        print(f"Purge failed: {e}")

if __name__ == "__main__":
    asyncio.run(nuke_remote_audit_log())
