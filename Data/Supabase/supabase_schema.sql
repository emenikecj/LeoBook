-- GLOBAL SUPABASE SCHEMA (LeoBook)
-- This file serves as the single source of truth for the database schema.
-- v1.2: Added DROP POLICY IF EXISTS for full idempotency.

-- =============================================================================
-- 1. EXTENSIONS & SETUP
-- =============================================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- 2. USER MANAGEMENT (Public Profiles)
-- =============================================================================
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID REFERENCES auth.users(id) ON DELETE CASCADE PRIMARY KEY,
    email TEXT,
    username TEXT UNIQUE,
    full_name TEXT,
    avatar_url TEXT,
    tier TEXT DEFAULT 'free',
    credits INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW();

-- Idempotent Policies for profiles
DROP POLICY IF EXISTS "Users can view own profile" ON public.profiles;
CREATE POLICY "Users can view own profile" ON public.profiles FOR SELECT USING (auth.uid() = id);

DROP POLICY IF EXISTS "Users can update own profile" ON public.profiles;
CREATE POLICY "Users can update own profile" ON public.profiles FOR UPDATE USING (auth.uid() = id);

-- Trigger for new user
CREATE OR REPLACE FUNCTION public.handle_new_user() 
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.profiles (id, email, full_name, avatar_url)
  VALUES (new.id, new.email, new.raw_user_meta_data->>'full_name', new.raw_user_meta_data->>'avatar_url');
  RETURN new;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created AFTER INSERT ON auth.users FOR EACH ROW EXECUTE PROCEDURE public.handle_new_user();

-- =============================================================================
-- 3. CUSTOM RULE ENGINE
-- =============================================================================
CREATE TABLE IF NOT EXISTS public.custom_rules (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    logic JSONB DEFAULT '{}'::jsonb NOT NULL,
    priority INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE public.custom_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.custom_rules ADD COLUMN IF NOT EXISTS last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW();
ALTER TABLE public.custom_rules ADD COLUMN IF NOT EXISTS is_default BOOLEAN DEFAULT false;
ALTER TABLE public.custom_rules ADD COLUMN IF NOT EXISTS scope JSONB DEFAULT '{}'::jsonb;
ALTER TABLE public.custom_rules ADD COLUMN IF NOT EXISTS accuracy JSONB DEFAULT '{}'::jsonb;
ALTER TABLE public.custom_rules ADD COLUMN IF NOT EXISTS backtest_csv_url TEXT;

-- Idempotent Policies for custom_rules
DROP POLICY IF EXISTS "Users can fully manage own rules" ON public.custom_rules;
CREATE POLICY "Users can fully manage own rules" ON public.custom_rules FOR ALL USING (auth.uid() = user_id);

CREATE TABLE IF NOT EXISTS public.rule_executions (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    rule_id UUID REFERENCES public.custom_rules(id) ON DELETE CASCADE,
    fixture_id TEXT,
    user_id UUID REFERENCES public.profiles(id),
    result JSONB,
    executed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE public.rule_executions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rule_executions ADD COLUMN IF NOT EXISTS last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW();

-- Idempotent Policies for rule_executions
DROP POLICY IF EXISTS "Users can view own rule executions" ON public.rule_executions;
CREATE POLICY "Users can view own rule executions" ON public.rule_executions FOR SELECT USING (auth.uid() = user_id);

-- =============================================================================
-- 4. DATA STORE (Core Tables)
-- =============================================================================

-- Region/League
CREATE TABLE IF NOT EXISTS public.region_league (
    rl_id TEXT PRIMARY KEY,
    region TEXT,
    region_flag TEXT,
    region_url TEXT,
    league TEXT,
    league_crest TEXT,
    league_url TEXT,
    date_updated TEXT,
    country TEXT,
    logo_url TEXT,
    other_names JSONB DEFAULT '[]',
    abbreviations JSONB DEFAULT '[]',
    search_terms TEXT[] DEFAULT ARRAY[]::TEXT[],
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
ALTER TABLE public.region_league ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.region_league ADD COLUMN IF NOT EXISTS last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW();

DROP POLICY IF EXISTS "Public Read Access RegionLeague" ON public.region_league;
CREATE POLICY "Public Read Access RegionLeague" ON public.region_league FOR SELECT USING (true);

-- Teams
CREATE TABLE IF NOT EXISTS public.teams (
    team_id TEXT PRIMARY KEY,
    team_name TEXT,
    rl_ids TEXT,
    team_crest TEXT,
    team_url TEXT,
    country TEXT,
    city TEXT,
    other_names JSONB DEFAULT '[]',
    abbreviations JSONB DEFAULT '[]',
    search_terms TEXT[] DEFAULT ARRAY[]::TEXT[],
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
ALTER TABLE public.teams ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.teams ADD COLUMN IF NOT EXISTS last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW();

DROP POLICY IF EXISTS "Public Read Access Teams" ON public.teams;
CREATE POLICY "Public Read Access Teams" ON public.teams FOR SELECT USING (true);

-- Schedules
CREATE TABLE IF NOT EXISTS public.schedules (
    fixture_id TEXT PRIMARY KEY,
    date TEXT,
    match_time TEXT,
    region_league TEXT,
    home_team TEXT,
    away_team TEXT,
    home_team_id TEXT,
    away_team_id TEXT,
    home_score TEXT,
    away_score TEXT,
    match_status TEXT,
    status TEXT,
    match_link TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
ALTER TABLE public.schedules ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.schedules ADD COLUMN IF NOT EXISTS status TEXT;
ALTER TABLE public.schedules ADD COLUMN IF NOT EXISTS last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW();

DROP POLICY IF EXISTS "Public Read Access Schedules" ON public.schedules;
CREATE POLICY "Public Read Access Schedules" ON public.schedules FOR SELECT USING (true);

-- Predictions
CREATE TABLE IF NOT EXISTS public.predictions (
    fixture_id TEXT PRIMARY KEY,
    date TEXT,
    match_time TEXT,
    region_league TEXT,
    home_team TEXT,
    away_team TEXT,
    home_team_id TEXT,
    away_team_id TEXT,
    prediction TEXT,
    confidence TEXT,
    reason TEXT,
    xg_home TEXT,
    xg_away TEXT,
    btts TEXT,
    over_2_5 TEXT,
    best_score TEXT,
    top_scores TEXT,
    home_form_n TEXT,
    away_form_n TEXT,
    home_tags TEXT,
    away_tags TEXT,
    h2h_tags TEXT,
    standings_tags TEXT,
    h2h_count TEXT,
    form_count TEXT,
    actual_score TEXT,
    outcome_correct TEXT,
    generated_at TEXT,
    status TEXT,
    match_link TEXT,
    odds TEXT,
    market_reliability_score TEXT,
    home_crest_url TEXT,
    away_crest_url TEXT,
    is_recommended TEXT,
    recommendation_score TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
ALTER TABLE public.predictions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.predictions ADD COLUMN IF NOT EXISTS last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW();

DROP POLICY IF EXISTS "Public Read Access Predictions" ON public.predictions;
CREATE POLICY "Public Read Access Predictions" ON public.predictions FOR SELECT USING (true);

-- Standings
CREATE TABLE IF NOT EXISTS public.standings (
    standings_key TEXT PRIMARY KEY,
    region_league TEXT,
    position INTEGER,
    team_name TEXT,
    team_id TEXT,
    played INTEGER,
    wins INTEGER,
    draws INTEGER,
    losses INTEGER,
    goals_for INTEGER,
    goals_against INTEGER,
    goal_difference INTEGER,
    points INTEGER,
    url TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
ALTER TABLE public.standings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.standings ADD COLUMN IF NOT EXISTS last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW();

DROP POLICY IF EXISTS "Public Read Access Standings" ON public.standings;
CREATE POLICY "Public Read Access Standings" ON public.standings FOR SELECT USING (true);

-- FB Matches
CREATE TABLE IF NOT EXISTS public.fb_matches (
    site_match_id TEXT PRIMARY KEY,
    date TEXT,
    time TEXT,
    home_team TEXT,
    away_team TEXT,
    league TEXT,
    url TEXT,
    last_extracted TEXT,
    fixture_id TEXT,
    matched TEXT,
    odds TEXT,
    booking_status TEXT,
    booking_details TEXT,
    booking_code TEXT,
    booking_url TEXT,
    status TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
ALTER TABLE public.fb_matches ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fb_matches ADD COLUMN IF NOT EXISTS last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW();

DROP POLICY IF EXISTS "Public Read Access FBMatches" ON public.fb_matches;
CREATE POLICY "Public Read Access FBMatches" ON public.fb_matches FOR SELECT USING (true);

-- =============================================================================
-- 5. UTILITY & MAINTENANCE
-- =============================================================================
CREATE OR REPLACE FUNCTION update_last_updated_column()
RETURNS TRIGGER AS $$
BEGIN
   -- Robustly check for column existence before setting
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
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_profiles_last_updated ON public.profiles;
CREATE TRIGGER update_profiles_last_updated BEFORE UPDATE ON public.profiles FOR EACH ROW EXECUTE PROCEDURE update_last_updated_column();

DROP TRIGGER IF EXISTS update_rules_last_updated ON public.custom_rules;
CREATE TRIGGER update_rules_last_updated BEFORE UPDATE ON public.custom_rules FOR EACH ROW EXECUTE PROCEDURE update_last_updated_column();
-- =============================================================================
-- 6. REPORTING & AUDIT
-- =============================================================================

-- Accuracy Reports
CREATE TABLE IF NOT EXISTS public.accuracy_reports (
    report_id TEXT PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    volume INTEGER DEFAULT 0,
    win_rate DECIMAL(5,2) DEFAULT 0,
    return_pct DECIMAL(5,2) DEFAULT 0,
    period TEXT DEFAULT 'last_24h',
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
ALTER TABLE public.accuracy_reports ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Public Read Access AccuracyReports" ON public.accuracy_reports;
CREATE POLICY "Public Read Access AccuracyReports" ON public.accuracy_reports FOR SELECT USING (true);

-- Audit Log
CREATE TABLE IF NOT EXISTS public.audit_log (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    event_type TEXT NOT NULL,
    description TEXT,
    balance_before DECIMAL(15,2),
    balance_after DECIMAL(15,2),
    stake DECIMAL(15,2),
    status TEXT DEFAULT 'success',
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
-- We use a UUID primary key to avoid ON CONFLICT errors on duplicate timestamps.
ALTER TABLE public.audit_log ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Public Read Access AuditLog" ON public.audit_log;
CREATE POLICY "Public Read Access AuditLog" ON public.audit_log FOR SELECT USING (true);

-- Triggers for last_updated
DROP TRIGGER IF EXISTS update_reports_last_updated ON public.accuracy_reports;
CREATE TRIGGER update_reports_last_updated BEFORE UPDATE ON public.accuracy_reports FOR EACH ROW EXECUTE PROCEDURE update_last_updated_column();

DROP TRIGGER IF EXISTS update_audit_last_updated ON public.audit_log;
CREATE TRIGGER update_audit_last_updated BEFORE UPDATE ON public.audit_log FOR EACH ROW EXECUTE PROCEDURE update_last_updated_column();

-- grants
GRANT SELECT ON public.accuracy_reports TO anon, authenticated;
GRANT SELECT ON public.audit_log TO anon, authenticated;

-- MIGRATION: Search Dictionary Upgrade
ALTER TABLE public.teams ADD COLUMN IF NOT EXISTS stadium TEXT;
ALTER TABLE public.teams ADD COLUMN IF NOT EXISTS search_terms TEXT[];
ALTER TABLE public.region_league ADD COLUMN IF NOT EXISTS search_terms TEXT[];

-- =============================================================================
-- LIVE SCORES TABLE
-- =============================================================================
CREATE TABLE IF NOT EXISTS public.live_scores (
    fixture_id TEXT PRIMARY KEY,
    home_team TEXT,
    away_team TEXT,
    home_score TEXT,
    away_score TEXT,
    minute TEXT,
    status TEXT,
    region_league TEXT,
    match_link TEXT,
    timestamp TIMESTAMP WITH TIME ZONE,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE public.live_scores ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Public Read Access LiveScores" ON public.live_scores;
CREATE POLICY "Public Read Access LiveScores" ON public.live_scores FOR SELECT USING (true);

DROP TRIGGER IF EXISTS update_livescores_last_updated ON public.live_scores;
CREATE TRIGGER update_livescores_last_updated BEFORE UPDATE ON public.live_scores FOR EACH ROW EXECUTE PROCEDURE update_last_updated_column();

GRANT SELECT ON public.live_scores TO anon, authenticated;

-- MIGRATION: Add outcome_correct and actual_score to predictions
ALTER TABLE public.predictions ADD COLUMN IF NOT EXISTS outcome_correct TEXT;
ALTER TABLE public.predictions ADD COLUMN IF NOT EXISTS actual_score TEXT;
ALTER TABLE public.predictions ADD COLUMN IF NOT EXISTS home_score TEXT;
ALTER TABLE public.predictions ADD COLUMN IF NOT EXISTS away_score TEXT;

-- MIGRATION: Search Dictionary enrichment columns
ALTER TABLE public.region_league ADD COLUMN IF NOT EXISTS country TEXT;
ALTER TABLE public.region_league ADD COLUMN IF NOT EXISTS logo_url TEXT;
ALTER TABLE public.teams ADD COLUMN IF NOT EXISTS country TEXT;
ALTER TABLE public.teams ADD COLUMN IF NOT EXISTS city TEXT;

-- =============================================================================
-- LEARNING WEIGHTS TABLE (Per-League Adaptive Weights)
-- =============================================================================
CREATE TABLE IF NOT EXISTS public.learning_weights (
    region_league TEXT PRIMARY KEY,
    weights JSONB NOT NULL DEFAULT '{}'::jsonb,
    confidence_calibration JSONB NOT NULL DEFAULT '{"Very High": 0.70, "High": 0.60, "Medium": 0.50, "Low": 0.40}'::jsonb,
    predictions_analyzed INTEGER DEFAULT 0,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE public.learning_weights ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Public Read Access LearningWeights" ON public.learning_weights;
CREATE POLICY "Public Read Access LearningWeights" ON public.learning_weights FOR SELECT USING (true);

DROP TRIGGER IF EXISTS update_learning_weights_last_updated ON public.learning_weights;
CREATE TRIGGER update_learning_weights_last_updated BEFORE UPDATE ON public.learning_weights FOR EACH ROW EXECUTE PROCEDURE update_last_updated_column();

GRANT SELECT ON public.learning_weights TO anon, authenticated;
