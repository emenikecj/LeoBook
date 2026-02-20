"""Run migration ALTER statements against Supabase via REST RPC."""
import os, httpx
from dotenv import load_dotenv
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise SystemExit("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY")

ALTERS = [
    "ALTER TABLE public.region_league ADD COLUMN IF NOT EXISTS country TEXT;",
    "ALTER TABLE public.region_league ADD COLUMN IF NOT EXISTS logo_url TEXT;",
    "ALTER TABLE public.teams ADD COLUMN IF NOT EXISTS country TEXT;",
    "ALTER TABLE public.teams ADD COLUMN IF NOT EXISTS city TEXT;",
]

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}

# Use the PostgREST rpc endpoint to run raw SQL via a helper function,
# or fall back to the supabase-py client.
from supabase import create_client
sb = create_client(SUPABASE_URL, SUPABASE_KEY)

for sql in ALTERS:
    try:
        sb.rpc("exec_sql", {"query": sql}).execute()
        print(f"  OK: {sql}")
    except Exception as e:
        print(f"  WARN: RPC method not available ({e})")
        print("  → Run these manually in the Supabase SQL Editor:")
        for s in ALTERS:
            print(f"    {s}")
        break

print("\nDone.")
