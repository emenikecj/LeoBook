# asset_manager.py: asset_manager.py: Module for Asset Synchronization.
# Part of LeoBook Assets Module
#
# Functions: sync_team_assets(), sync_league_assets(), main()

import os
import logging
import requests
import pandas as pd
from pathlib import Path
from typing import Optional
from Data.Access.supabase_client import get_supabase_client
from Data.Access.db_helpers import DB_DIR

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
PROJECT_ROOT = Path(__file__).parent.parent.parent
TEAMS_CSV = PROJECT_ROOT / "Data" / "Store" / "teams.csv"
LEAGUES_CSV = PROJECT_ROOT / "Data" / "Store" / "region_league.csv"

def download_image(url: str, save_path: Path) -> bool:
    """Downloads an image from a URL and saves it temporarily."""
    if not url or url.lower() in ["unknown", "unknown url", "none"]:
        return False
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        with open(save_path, 'wb') as f:
            f.write(response.content)
        return True
    except Exception as e:
        logger.error(f"[x] Error downloading {url}: {e}")
        return False

def upload_to_supabase(storage_client, bucket_name: str, file_path: Path, remote_filename: str):
    """Uploads a file to Supabase storage bucket."""
    try:
        with open(file_path, 'rb') as f:
            # Check if file exists in bucket (simple list check or just try upload)
            # For iteration speed, we just try to upload. If it exists, it might fail or overwrite.
            # Upsert is preferred.
            res = storage_client.from_(bucket_name).upload(
                path=remote_filename,
                file=f,
                file_options={"cache-control": "3600", "upsert": "true"}
            )
            logger.info(f"[+] Successfully uploaded {remote_filename} to {bucket_name}")
            return res
    except Exception as e:
        # If it's a conflict or other error, log it.
        # Supabase storage upload can be tricky with existing files.
        logger.error(f"[x] Error uploading {remote_filename} to {bucket_name}: {e}")
        return None

def ensure_bucket_exists(storage_client, bucket_name: str):
    """Checks if a bucket exists, creates it if it doesn't."""
    try:
        buckets = storage_client.list_buckets()
        bucket_names = [b.name for b in buckets]
        if bucket_name not in bucket_names:
            logger.info(f"[*] Bucket {bucket_name} not found. Creating...")
            storage_client.create_bucket(bucket_name, options={"public": True})
            logger.info(f"[+] Bucket {bucket_name} created successfully.")
        else:
            logger.info(f"[*] Bucket {bucket_name} already exists.")
        return True
    except Exception as e:
        logger.error(f"[x] Error ensuring bucket {bucket_name} exists: {e}")
        # We might still proceed as upload might work if it exists but list fails
        return False

def sync_team_assets(limit: Optional[int] = None):
    """Syncs team crests to Supabase storage."""
    client = get_supabase_client()
    if not client:
        return

    df = pd.read_csv(TEAMS_CSV)
    if limit:
        df = df.head(limit)
        
    storage = client.storage
    ensure_bucket_exists(storage, "teams")

    temp_dir = Path("temp_assets")
    temp_dir.mkdir(exist_ok=True)

    logger.info(f"[*] Starting team assets sync. Total teams: {len(df)}")
    
    for _, row in df.iterrows():
        team_id = row['team_id']
        url = row['team_crest']
        
        if team_id == "Unknown" or not url or url.lower() in ["unknown", "unknown url"]:
            continue
            
        # Standardize filename (always .png for consistency, or extract if needed)
        # Most flashscore images are .png
        filename = f"{team_id}.png"
        local_path = temp_dir / filename
        
        if download_image(url, local_path):
            upload_to_supabase(storage, "teams", local_path, filename)
            # Option to delete local file after upload
            os.remove(local_path)
            
    if temp_dir.exists():
        try:
            temp_dir.rmdir() # Only works if empty
        except:
            pass

def sync_league_assets(limit: Optional[int] = None):
    """Syncs league crests to Supabase storage."""
    client = get_supabase_client()
    if not client:
        return

    df = pd.read_csv(LEAGUES_CSV)
    if limit:
        df = df.head(limit)
        
    storage = client.storage
    ensure_bucket_exists(storage, "leagues")

    temp_dir = Path("temp_assets_leagues")
    temp_dir.mkdir(exist_ok=True)

    logger.info(f"[*] Starting league assets sync. Total leagues: {len(df)}")

    for _, row in df.iterrows():
        league_id = row['league_id']
        url = row['league_crest']
        
        if league_id == "Unknown" or not url or url.lower() in ["unknown", "unknown url", "none"]:
            continue
            
        filename = f"{league_id}.png"
        local_path = temp_dir / filename
        
        if download_image(url, local_path):
            upload_to_supabase(storage, "leagues", local_path, filename)
            os.remove(local_path)

    if temp_dir.exists():
        try:
            temp_dir.rmdir()
        except:
            pass

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Sync assets to Supabase Storage.")
    parser.add_argument("--teams", action="store_true", help="Sync team assets")
    parser.add_argument("--leagues", action="store_true", help="Sync league assets")
    parser.add_argument("--all", action="store_true", help="Sync all assets")
    parser.add_argument("--limit", type=int, help="Limit number of assets to sync for testing")
    
    args = parser.parse_args()
    
    if args.all or args.teams:
        sync_team_assets(limit=args.limit)
    if args.all or args.leagues:
        sync_league_assets(limit=args.limit)
    
    if not (args.all or args.teams or args.leagues):
        parser.print_help()
