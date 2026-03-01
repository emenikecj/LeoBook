# Supabase Setup Guide

> **Version**: 4.0 · **Last Updated**: 2026-03-01

## Quick Setup (5 minutes)

### Step 1: Create Supabase Account
1. Go to **https://supabase.com**
2. Click **"Start your project"**
3. Sign up with **GitHub** (recommended) or email

### Step 2: Create Project
1. Click **"New Project"**
2. Fill in details:
   - **Name**: `leobook-production`
   - **Database Password**: Generate a strong one (save it securely!)
   - **Region**: Choose closest to your server (e.g., **Europe (Frankfurt)** for Aba, Nigeria)
   - **Pricing Plan**: Free tier is sufficient
3. Click **"Create new project"**
4. ⏳ Wait ~2 minutes for project to initialize

### Step 3: Run Database Schema
1. Once project is ready, go to **SQL Editor** (left sidebar)
2. Click **"New Query"**
3. Copy the entire contents of [`Data/Supabase/supabase_schema.sql`](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Data/Supabase/supabase_schema.sql)
4. Paste into the editor
5. Click **"Run"** (or press Ctrl+Enter)
6. ✅ You should see "Success. No rows returned"

### Step 4: Get API Credentials
1. Go to **Project Settings** (gear icon in left sidebar)
2. Click **"API"** in the settings menu
3. Copy these values:

   **Project URL:**
   ```
   https://xxxxxxxxxxxxx.supabase.co
   ```

   **Anon/Public Key** (starts with `eyJhbGc...`):
   ```
   eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
   ```

   **Service Role Key** (for Python backend, starts with `eyJhbGc...`):
   ```
   eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
   ```
   ⚠️ **Keep Service Role Key secret!** Never commit it to GitHub!

### Step 5: Configure Environment Files

**Python Backend** (`.env` in project root):
```env
SUPABASE_URL=https://xxxxxxxxxxxxx.supabase.co
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1...
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1...
```

**Flutter App** (`leobookapp/.env`):
```env
SUPABASE_URL=https://xxxxxxxxxxxxx.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1...
```

> ⚠️ Both `.env` files are in `.gitignore`. NEVER commit credentials!

---

## How Sync Works (v4.0)

LeoBook v4.0 uses **High-Velocity Bi-Directional Syncing** — all tables sync both ways using timestamp-based conflict resolution. No manual scripts needed.

### Sync Architecture
```
Leo.py runs SyncManager automatically:
  ① sync_on_startup()    — Bi-directional merge: compare timestamps, pull newer remote, push newer local
  ② run_full_sync()      — Called 5+ times per cycle (after each chapter page)
  ③ batch_upsert()       — Real-time micro-pushes during match processing
```

### Key Files
| File | Purpose |
|------|---------|
| `Data/Access/sync_manager.py` | `SyncManager` — bi-directional UPSERT engine with pandas delta detection |
| `Data/Access/supabase_client.py` | Supabase client singleton factory |
| `Data/Supabase/push_schema.sql` | Auto-provisioning schema definition |

### Tables Synced (12 tables, all bi-directional)

| Table | Source CSV | Unique Key |
|-------|-----------|------------|
| `predictions` | `predictions.csv` | `fixture_id` |
| `schedules` | `schedules.csv` | `fixture_id` |
| `teams` | `teams.csv` | `team_id` |
| `region_league` | `region_league.csv` | `league_id` |
| `standings` | `standings.csv` | `standings_key` |
| `fb_matches` | `fb_matches.csv` | `site_match_id` |
| `profiles` | `profiles.csv` | `id` |
| `custom_rules` | `custom_rules.csv` | `id` |
| `rule_executions` | `rule_executions.csv` | `id` |
| `accuracy_reports` | `accuracy_reports.csv` | `report_id` |
| `audit_log` | `audit_log.csv` | `id` |
| `live_scores` | `live_scores.csv` | `fixture_id` |

### Sync Frequency per Leo.py Cycle
1. **Prologue P1**: `sync_on_startup()` — full bi-directional merge with timestamp normalization
2. **Prologue P2**: `run_full_sync()` — accuracy report push
3. **Ch1 P1 (Per-Match Workers)**:
   - **Real-time Enrichment**: League/team metadata pushed immediately after extraction
   - **Micro-Batch Sync**: Predictions synced to Supabase every 10 matches
4. **Ch1 P2, P3, Ch2, Ch3**: `run_full_sync()` after each page
5. **Live Streamer**: Delta-only `batch_upsert()` + `batch_delete()` every 60s

---

## Verify Setup

### Check Tables Exist
```sql
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
```

Expected: `predictions`, `schedules`, `standings`, `teams`, `region_league`, `fb_matches`, `profiles`, `custom_rules`, `rule_executions`, `accuracy_reports`, `audit_log`, `live_scores`

### Check Data After First Leo.py Cycle
```sql
SELECT COUNT(*) as total_predictions FROM predictions;
SELECT COUNT(*) as total_schedules FROM schedules;
SELECT * FROM predictions ORDER BY generated_at DESC LIMIT 5;
```

### Test Flutter App Query
```sql
SELECT * FROM predictions
WHERE date >= CURRENT_DATE
  AND date <= CURRENT_DATE + INTERVAL '14 days'
ORDER BY date ASC
LIMIT 10;
```

---

## Security Best Practices

1. ✅ **Never commit** `.env` files
2. ✅ **Service Role Key** — only used by Python backend (has full write access)
3. ✅ **Anon Key** — used by Flutter app (read-only via Row Level Security)
4. ✅ **Rotate keys** if compromised: Supabase Dashboard → API → Reset
5. ✅ **Enable RLS** on all tables for production deployment

---

## Troubleshooting

| Error | Solution |
|-------|---------|
| "Missing environment variables" | Create `.env` file with `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` |
| "Connection timeout" | Check internet connection and Supabase URL |
| "Permission denied" | Verify you're using `SERVICE_ROLE_KEY` (not `ANON_KEY`) in Python backend |
| "Table not found" | Run `supabase_schema.sql` in SQL Editor |
| "Duplicate key violation" | Normal during UPSERT — `SyncManager` resolves automatically |

---

## Flutter App Configuration

The Flutter app reads Supabase credentials from `leobookapp/.env` via the `flutter_dotenv` package. Configuration is loaded in:
- [`supabase_config.dart`](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/leobookapp/lib/core/config/supabase_config.dart) — reads env vars
- [`main.dart`](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/leobookapp/lib/main.dart) — initializes Supabase client on startup

The app uses the **Anon Key** and reads data via:
- [`data_repository.dart`](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/leobookapp/lib/data/repositories/data_repository.dart) — main data fetching
- [`news_repository.dart`](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/leobookapp/lib/data/repositories/news_repository.dart) — news feed
