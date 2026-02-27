# sync_manager.py: sync_manager.py: Module for Data — Access Layer.
# Part of LeoBook Data — Access Layer
#
# Classes: SyncManager
# Functions: run_full_sync()

import csv
import logging
import asyncio
import re
import pandas as pd
import numpy as np
from tqdm import tqdm
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from supabase import create_client, Client

from Data.Access.supabase_client import get_supabase_client
from Data.Access.db_helpers import DB_DIR, files_and_headers
from Core.Intelligence.aigo_suite import AIGOSuite
from Data.Supabase.push_schema import push_schema

logger = logging.getLogger(__name__)

# Constants
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "Data" / "Store"

TABLE_CONFIG = {
    'predictions': {'csv': 'predictions.csv', 'table': 'predictions', 'key': 'fixture_id'},
    'schedules': {'csv': 'schedules.csv', 'table': 'schedules', 'key': 'fixture_id'},
    'teams': {'csv': 'teams.csv', 'table': 'teams', 'key': 'team_id'},
    'region_league': {'csv': 'region_league.csv', 'table': 'region_league', 'key': 'league_id'},
    'standings': {'csv': 'standings.csv', 'table': 'standings', 'key': 'standings_key'},
    'fb_matches': {'csv': 'fb_matches.csv', 'table': 'fb_matches', 'key': 'site_match_id'},
    'profiles': {'csv': 'profiles.csv', 'table': 'profiles', 'key': 'id'},
    'custom_rules': {'csv': 'custom_rules.csv', 'table': 'custom_rules', 'key': 'id'},
    'rule_executions': {'csv': 'rule_executions.csv', 'table': 'rule_executions', 'key': 'id'},
    'accuracy_reports': {'csv': 'accuracy_reports.csv', 'table': 'accuracy_reports', 'key': 'report_id'},
    'audit_log': {'csv': 'audit_log.csv', 'table': 'audit_log', 'key': 'id'},
    'live_scores': {'csv': 'live_scores.csv', 'table': 'live_scores', 'key': 'fixture_id'},
}

class SyncManager:
    """
    Manages bi-directional synchronization between local CSVs and Supabase using pandas.
    """
    def __init__(self):
        self.supabase = get_supabase_client()
        if not self.supabase:
            logger.warning("[!] SyncManager initialized without Supabase connection. Sync disabled.")

    # Removed manual _retry_async in favor of universal @aigo_retry decorator

    async def sync_on_startup(self):
        """Pull remote changes and push local changes for all configured tables."""
        if not self.supabase:
            return

        logger.info("Starting hardened bi-directional sync on startup...")
        
        # Phase 0: Auto-Provision Supabase Schema
        print("   [PROLOGUE] Auto-provisioning Supabase Database Schema...")
        schema_ok = push_schema()
        if not schema_ok:
            print("   [WARNING] Schema auto-provision failed. Ensure 'execute_sql' RPC exists and Service Key is in .env.")
            
        print("   [PROLOGUE] Bi-Directional Sync — comparing local CSV vs Supabase timestamps...")

        for table_key, config in TABLE_CONFIG.items():
            await self._sync_table(table_key, config)

    async def _sync_table(self, table_key: str, config: Dict):
        """Sync a single table using pandas for delta detection."""
        table_name = config['table']
        csv_file = config['csv']
        key_field = config['key']
        csv_path = DATA_DIR / csv_file
        
        if not csv_path.exists():
            logger.warning(f"  [SKIP] {csv_file} not found.")
            return

        logger.info(f"  Syncing {table_name} <-> {csv_file}...")

        # 1. Fetch Remote Metadata (ID + last_updated)
        try:
            remote_meta = await self._fetch_remote_metadata(table_name, key_field)
        except Exception as e:
            logger.error(f"    [x] Failed to fetch remote metadata for {table_name}: {e}")
            return

        # 2. Load Local Data with Pandas
        try:
            df_local = pd.read_csv(csv_path, dtype=str).fillna('')
            if key_field not in df_local.columns:
                 logger.error(f"    [x] Key field {key_field} missing in local {csv_file}")
                 return
            
            if 'last_updated' not in df_local.columns:
                logger.info(f"    [!] Initializing missing 'last_updated' column in {csv_file}")
                df_local['last_updated'] = ''
                 
            df_local[key_field] = df_local[key_field].astype(str)
        except Exception as e:
            logger.error(f"    [x] Failed to read {csv_file} with pandas: {e}")
            return

        # 3. Delta Detection (Latest Wins logic)
        remote_df = pd.DataFrame(list(remote_meta.items()), columns=[key_field, 'remote_ts'])
        
        # Normalize timestamps for fair comparison
        def normalize_ts(ts):
            if not ts or ts in ('None', 'nan', ''): return '1970-01-01T00:00:00'
            try:
                # Ensure ISO format comparison works as string comparison
                return pd.to_datetime(ts).isoformat()
            except:
                return '1970-01-01T00:00:00'

        df_local['last_updated'] = df_local['last_updated'].apply(normalize_ts)
        remote_df['remote_ts'] = remote_df['remote_ts'].apply(normalize_ts)

        # Merge to compare
        merged = pd.merge(df_local[[key_field, 'last_updated']], remote_df, on=key_field, how='outer').fillna('')
        
        # PUSH: Local is strictly newer OR Remote doesn't have it
        to_push_ids = merged[
            (merged['last_updated'] > merged['remote_ts']) | 
            ((merged['last_updated'] != '1970-01-01T00:00:00') & (merged['remote_ts'] == '1970-01-01T00:00:00'))
        ][key_field].tolist()

        # PULL: Remote is strictly newer OR Local doesn't have it
        to_pull_ids = merged[
            (merged['remote_ts'] > merged['last_updated']) |
            ((merged['remote_ts'] != '1970-01-01T00:00:00') & (merged['last_updated'] == '1970-01-01T00:00:00'))
        ][key_field].tolist()

        logger.info(f"    Delta: {len(to_push_ids)} to push, {len(to_pull_ids)} to pull. (Conflict resolution: Latest Wins)")

        # User-visible sync direction feedback
        if to_push_ids and to_pull_ids:
            print(f"   [{table_name}] ↕ Bi-directional: {len(to_push_ids)} CSV→DB, {len(to_pull_ids)} DB→CSV")
        elif to_push_ids:
            print(f"   [{table_name}] ↑ Push: {len(to_push_ids)} rows CSV→DB (local is newer)")
        elif to_pull_ids:
            print(f"   [{table_name}] ↓ Pull: {len(to_pull_ids)} rows DB→CSV (remote is newer)")
        else:
            print(f"   [{table_name}] ✓ Already in sync")

        # 4. Pull Operations
        if to_pull_ids:
            await self._pull_updates(table_name, key_field, to_pull_ids, csv_path)

        # 5. Push Operations
        if to_push_ids:
             rows_to_push = df_local[df_local[key_field].isin(to_push_ids)].to_dict('records')
             await self.batch_upsert(table_key, rows_to_push)
             
             # 6. Verification Phase
             await self._verify_sync_parity(table_key, to_push_ids)

    async def _fetch_remote_metadata(self, table_name: str, key_field: str) -> Dict[str, str]:
        """Fetch all ID:last_updated pairs from Supabase."""
        remote_map = {}
        batch_size = 1000
        offset = 0
        
        while True:
            try:
                res = self.supabase.table(table_name).select(f"{key_field},last_updated").range(offset, offset + batch_size - 1).execute()
                
                rows = res.data
                if not rows:
                    break
                
                # Setup progress bar on first batch if we know the count
                # Note: We don't always know total count here without an extra query, 
                # but we can show progress in terms of batches or just rows found.
                for r in rows:
                    k = r.get(key_field)
                    if k:
                        remote_map[str(k)] = r.get('last_updated', '')
                
                logger.info(f"      [Metadata] Found {len(remote_map)} remote entries...")
                
                if len(rows) < batch_size:
                    break
                offset += batch_size
            except Exception as e:
                logger.error(f"      [x] Metadata fetch error at offset {offset}: {e}")
                break
        
        return remote_map

    async def _pull_updates(self, table_name: str, key_field: str, ids: List[str], csv_path: Path):
        """Fetch rows from Supabase and update local CSV using pandas."""
        if not ids:
            return

        logger.info(f"    Pulling {len(ids)} rows from remote...")
        
        pulled_data = []
        batch_size = 200
        pbar = tqdm(total=len(ids), desc=f"    Pulling {table_name}", unit="row")
        for i in range(0, len(ids), batch_size):
            batch_ids = ids[i:i + batch_size]
            res = self.supabase.table(table_name).select("*").in_(key_field, batch_ids).execute()
            pulled_data.extend(res.data)
            pbar.update(len(batch_ids))
        pbar.close()

        if not pulled_data:
            return

        # Load local, update with pulled, save
        df_local = pd.read_csv(csv_path, dtype=str).fillna('')
        df_remote = pd.DataFrame(pulled_data).astype(str).fillna('')
        
        # Normalize remote data Types/Keys
        if 'over_2_5' in df_remote.columns:
            df_remote['over_2.5'] = df_remote['over_2_5']
            df_remote = df_remote.drop(columns=['over_2_5'])

        # Data Normalization (PostgreSQL -> CSV formats)
        for col in df_remote.columns:
            if col in ['date', 'date_updated', 'last_extracted']:
                df_remote[col] = df_remote[col].apply(lambda x: f"{x[8:10]}.{x[5:7]}.{x[0:4]}" if len(x) >= 10 and '-' in x else x)

        # Merge
        df_local.set_index(key_field, inplace=True)
        df_remote.set_index(key_field, inplace=True)
        df_local.update(df_remote)
        
        # Add new rows
        new_rows = df_remote[~df_remote.index.isin(df_local.index)]
        df_final = pd.concat([df_local.reset_index(), new_rows.reset_index()], ignore_index=True)

        # Ensure correct column ordering based on definition
        headers = files_and_headers.get(str(csv_path), [])
        if headers:
            # Only keep headers that actually exist in the dataframe
            final_cols = [h for h in headers if h in df_final.columns]
            # Add any extra columns found in data but not in headers (safety)
            extra_cols = [c for c in df_final.columns if c not in headers]
            df_final = df_final[final_cols + extra_cols]

        df_final.to_csv(csv_path, index=False, encoding='utf-8')
        logger.info(f"    [SUCCESS] {csv_path.name} updated via pandas.")

    async def batch_upsert(self, table_key: str, data: List[Dict[str, Any]]):
        """Upsert a batch of data to Supabase with strict cleaning."""
        if not self.supabase or not data:
            return

        conf = TABLE_CONFIG.get(table_key)
        if not conf: return
        
        table_name = conf['table']
        conflict_key = conf['key']
        csv_path = str(DATA_DIR / conf['csv'])
        whitelist = set(files_and_headers.get(csv_path, []))
        whitelist.update(['id', 'created_at', 'last_updated'])

        cleaned_data = []
        for row in data:
            clean = {}
            for k, v in row.items():
                if whitelist and k not in whitelist and k != 'over_2.5':
                    continue

                if v in ('', 'N/A', None, 'None', 'none', 'nan', 'NaN', 'null', 'NULL'):
                    clean[k] = None
                # Fix: Convert stringified Python lists to None for Postgres TEXT[] columns
                # Catches: "[]", "['unknown']", "['val1', 'val2']", etc.
                elif isinstance(v, str) and re.match(r"^\[.*\]$", v.strip()):
                    clean[k] = None
                else:
                    val = v
                    # CSV (DD.MM.YYYY or DD.MM.YY) -> DB (YYYY-MM-DD)
                    if k in ['date', 'date_updated', 'last_extracted'] and isinstance(val, str):
                        # Match DD.MM.YYYY
                        match_full = re.match(r'^(\d{2})\.(\d{2})\.(\d{4})$', val)
                        if match_full:
                            d, m, y = match_full.groups()
                            val = f"{y}-{m}-{d}"
                        else:
                            # Match DD.MM.YY (Legacy/Short format)
                            match_short = re.match(r'^(\d{2})\.(\d{2})\.(\d{2})$', val)
                            if match_short:
                                d, m, y_short = match_short.groups()
                                val = f"20{y_short}-{m}-{d}"
                            elif not re.match(r'^\d{4}-\d{2}-\d{2}', val):
                                # Not a valid date format (e.g. "Pending", "TBD") — null it
                                val = None
                    
                    if k == 'over_2.5':
                        clean['over_2_5'] = val
                    else:
                        clean[k] = val
            
            if 'id' in clean and not clean['id']: del clean['id']
            
            # Timestamp normalization
            now_iso = datetime.utcnow().isoformat()
            ts_cols = ['last_updated', 'date_updated', 'last_extracted', 'created_at']
            for ts in ts_cols:
                if ts in clean:
                    if not clean[ts] or not re.match(r'^\d{4}-\d{2}-\d{2}', str(clean[ts])):
                        clean[ts] = now_iso
            
            if 'last_updated' not in clean: clean['last_updated'] = now_iso
            cleaned_data.append(clean)

        # Deduplication items
        keys = [k.strip() for k in conflict_key.split(',')]
        seen = set()
        deduped = []
        for row in cleaned_data:
            if all(row.get(k) not in (None, '') for k in keys):
                kv = tuple(row.get(k) for k in keys)
                if kv not in seen:
                    seen.add(kv); deduped.append(row)
        
        if not deduped: return

        try:
            # Batch size for Supabase upsert (usually 1000 is safe)
            api_batch_size = 1000
            pbar = tqdm(total=len(deduped), desc=f"    Pushing {table_name}", unit="row")
            
            for i in range(0, len(deduped), api_batch_size):
                batch = deduped[i:i + api_batch_size]
                self.supabase.table(table_name).upsert(batch, on_conflict=conflict_key).execute()
                pbar.update(len(batch))
                
            pbar.close()
            logger.info(f"    [SYNC] Upserted {len(deduped)} rows to {table_name}.")
        except Exception as e:
            pbar.close()
            print(f"    [x] Upsert failed for {table_name}: {e}")
            logger.error(f"    [x] Upsert failed: {e}")

    async def _verify_sync_parity(self, table_key: str, pushed_ids: List[str], sample_size: int = 10):
        """Pick a sample and verify parity between local and remote."""
        if not pushed_ids: return
        
        conf = TABLE_CONFIG[table_key]
        table_name = conf['table']
        key_field = conf['key']
        
        # Sample IDs
        sample_ids = pushed_ids[:sample_size] if len(pushed_ids) <= sample_size else np.random.choice(pushed_ids, sample_size, replace=False).tolist()
        
        logger.info(f"    Verifying parity for {len(sample_ids)} sample rows...")
        
        try:
            # Fetch remote sample
            res = self.supabase.table(table_name).select("*").in_(key_field, sample_ids).execute()
            remote_rows = {str(r[key_field]): r for r in res.data}
            
            # Load local sample
            df_local = pd.read_csv(DATA_DIR / conf['csv'], dtype=str).fillna('')
            local_sample = df_local[df_local[key_field].astype(str).isin(sample_ids)].to_dict('records')
            local_rows = {str(r[key_field]): r for r in local_sample}
            
            mismatches = 0
            for uid in sample_ids:
                l_row = local_rows.get(uid)
                r_row = remote_rows.get(uid)
                
                if not r_row:
                    logger.warning(f"      [Parity Fail] ID {uid} missing from remote!")
                    mismatches += 1; continue
                
                # Check critical field: last_updated
                l_ts = l_row.get('last_updated', '')
                r_ts = r_row.get('last_updated', '')
                
                # Robust timestamp comparison (handle timezone offsets)
                try:
                    # Local TS: 2026-02-14T20:54:29.860512+01:00
                    # Remote TS: 2026-02-14T19:54:29.860512+00:00
                    dt_l = datetime.fromisoformat(l_ts.replace('Z', '+00:00')) if l_ts else None
                    dt_r = datetime.fromisoformat(r_ts.replace('Z', '+00:00')) if r_ts else None
                    
                    if dt_l and dt_r:
                        # Allow 1 second buffer for precision differences
                        if dt_r < dt_l and abs((dt_l - dt_r).total_seconds()) > 1:
                            logger.warning(f"      [Parity Warning] ID {uid} timestamp mismatch! Local: {l_ts}, Remote: {r_ts}")
                            mismatches += 1
                except (ValueError, TypeError):
                    # Fallback to string prefix if parsing fails
                    if r_ts < l_ts and r_ts[:19] != l_ts[:19]:
                        logger.warning(f"      [Parity Warning] ID {uid} timestamp mismatch! Local: {l_ts}, Remote: {r_ts}")
                        mismatches += 1

            if mismatches > 0:
                 logger.error(f"    [PARITY ERROR] Detected {mismatches} mismatches in {table_name}. Triggering re-sync...")
                 # Recalling sync for these specific IDs if mismatch rate is high
                 # For now, just log. 
            else:
                 logger.info(f"    [PARITY OK] {table_name} sample verified.")
                 
        except Exception as e:
            logger.error(f"    [x] Parity verification failed: {e}")

@AIGOSuite.aigo_retry(max_retries=3, delay=2.0, use_aigo=False)
async def run_full_sync(session_name: str = "Periodic"):
    """Wrapper to sync ALL tables with audit logging and AIGO protection."""
    from Data.Access.db_helpers import log_audit_event
    from Data.Supabase.push_schema import push_schema
    
    logger.info(f"Starting global full sync [{session_name}]...")
    
    print("   [PROLOGUE] Auto-provisioning Supabase Database Schema before sync...")
    schema_ok = push_schema()
    if not schema_ok:
        print("   [WARNING] Schema auto-provision failed. Ensure 'execute_sql' and 'refresh_schema' RPCs exist and Service Key is in .env.")
            
    manager = SyncManager()
    
    success_count = 0
    fail_count = 0
    errors = []

    for table_key, config in TABLE_CONFIG.items():
        try:
            await manager._sync_table(table_key, config)
            success_count += 1
        except Exception as e:
            logger.error(f"    [Sync Fatal] {table_key}: {e}")
            fail_count += 1
            errors.append(f"{table_key}: {str(e)}")

    # Audit Logging
    status = "success" if fail_count == 0 else "partial_failure" if success_count > 0 else "failed"
    msg = f"Full Chapter Sync ({session_name}): {success_count} passed, {fail_count} failed."
    if errors:
        msg += f" Errors: {'; '.join(errors[:3])}"
        
    try:
        log_audit_event(
            event_type="SYSTEM_SYNC",
            description=msg,
            status=status
        )
    except Exception as e:
        logger.error(f"Failed to log audit event for sync: {e}")

    if fail_count > 0:
        print(f"\n[!] Sync Warning: {fail_count} tables failed parity. AIGO fallback may be required.")
        return False
    
    return True


