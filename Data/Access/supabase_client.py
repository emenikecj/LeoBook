# supabase_client.py: supabase_client.py: Module for Data — Access Layer.
# Part of LeoBook Data — Access Layer
#
# Functions: get_supabase_client()

import os
import logging
from typing import Optional
from dotenv import load_dotenv
from supabase import create_client, Client

# Configure logging
logger = logging.getLogger(__name__)

# Singleton instance
_client: Optional[Client] = None

def get_supabase_client() -> Optional[Client]:
    """
    Get or create a Supabase client instance.
    Requires SUPABASE_URL and SUPABASE_SERVICE_KEY env vars.
    """
    global _client
    if _client:
        return _client

    load_dotenv()
    
    url = os.getenv("SUPABASE_URL")
    # Use Service Key for admin privileges (bypass RLS if needed for sync)
    key = os.getenv("SUPABASE_SERVICE_KEY") 
    
    if not url or not key:
        logger.warning("[!] SUPABASE_URL or SUPABASE_SERVICE_KEY missing. Sync disabled.")
        return None

    try:
        _client = create_client(url, key)
        return _client
    except Exception as e:
        logger.error(f"[x] Failed to initialize Supabase client: {e}")
        return None
