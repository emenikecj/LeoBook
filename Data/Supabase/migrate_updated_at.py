# migrate_updated_at.py: migrate_updated_at.py: Module for Data — Supabase Migrations.
# Part of LeoBook Data — Supabase Migrations
#

"""
One-time migration: Add updated_at column to tables that lack it,
and replace the trigger function with a robust version that checks
for column existence before setting.
"""
import os
import logging
from dotenv import load_dotenv
from supabase import create_client

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_KEY")

if not url or not key:
    print("[!] Missing SUPABASE_URL or SUPABASE_SERVICE_KEY")
    exit(1)

sb = create_client(url, key)

# --- Step 1: Add updated_at to tables that lack it ---
tables_needing_updated_at = [
    "accuracy_reports",
    "audit_log",
    "region_league",
    "teams",
    "schedules",
    "predictions",
    "standings",
    "fb_matches",
]

for table in tables_needing_updated_at:
    sql = f"ALTER TABLE public.{table} ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();"
    logger.info(f"  Adding updated_at to {table}...")
    try:
        sb.rpc("exec_sql", {"query": sql}).execute()
        logger.info(f"    [OK] {table}")
    except Exception as e:
        logger.warning(f"    [!] {table}: {e}")

# --- Step 2: Replace the trigger function with a robust version ---
robust_fn = """
CREATE OR REPLACE FUNCTION public.update_last_updated_column()
RETURNS TRIGGER AS $$
BEGIN
   IF EXISTS (
       SELECT 1 FROM information_schema.columns 
       WHERE table_schema = TG_TABLE_SCHEMA 
       AND table_name = TG_TABLE_NAME 
       AND column_name = 'updated_at'
   ) THEN
       NEW.updated_at = NOW();
   END IF;

   IF EXISTS (
       SELECT 1 FROM information_schema.columns 
       WHERE table_schema = TG_TABLE_SCHEMA 
       AND table_name = TG_TABLE_NAME 
       AND column_name = 'last_updated'
   ) THEN
       NEW.last_updated = NOW();
   END IF;

   RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

logger.info("\n  Replacing trigger function with robust version...")
try:
    sb.rpc("exec_sql", {"query": robust_fn}).execute()
    logger.info("    [OK] Trigger function updated.")
except Exception as e:
    logger.warning(f"    [!] Trigger function update: {e}")

print("\n[DONE] Migration complete. Re-run Leo.py to verify.")
