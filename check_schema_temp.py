import asyncio
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

async def check_tables():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    supabase = create_client(url, key)
    
    tables = ["teams", "region_league"]
    for table_name in tables:
        print(f"\nChecking table: {table_name}")
        try:
            res = supabase.table(table_name).select("*").limit(1).execute()
            if res.data:
                print(f"  Columns: {list(res.data[0].keys())}")
            else:
                print("  Table exists but is empty.")
        except Exception as e:
            print(f"  Error/Not Found: {e}")

if __name__ == "__main__":
    asyncio.run(check_tables())
