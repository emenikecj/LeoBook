# LeoBook Algorithm & Codebase Reference

> **Version**: 4.0 · **Last Updated**: 2026-03-01 · **Architecture**: High-Velocity Concurrent Architecture (Shared Locking + Per-Match Sequential Pipeline + Adaptive Learning)

This document maps the **execution flow** of [Leo.py](Leo.py) to specific files and functions.

---

## System Architecture

Leo.py is a **pure orchestrator**. It runs an infinite `while True` loop, splitting each cycle into phases:

```
Leo.py (Orchestrator) v4.0
├── Prologue P1 (Sequential Prerequisite):
│   └── Cloud Sync → Outcome Review → Accuracy Report
├── Concurrent Execution:
│   ├── Prologue P2: Accuracy Generation & Final Sync
│   └── Chapter 1→2 Pipeline:
│       ├── Ch1 P1: [Match Worker Node] × MAX_CONCURRENCY
│       │   └── H2H/Standings → League Enrichment → Search Dict → Prediction
│       ├── Ch1 P2: Odds Harvesting & URL Resolution
│       ├── Ch1 P3: Final Sync & Recommendations
│       ├── Ch2 P1: Automated Booking (if session healthy)
│       └── Ch2 P2: Funds & Withdrawal Check
├── Chapter 3 (Sequential Finality):
│   └── Chief Engineer Oversight → Backtest → Final Sync
└── Live Streamer: Isolated parallel task (always-on)
```

---

## Live Streamer (Isolated Parallel Task)

**Objective**: Absolute real-time parity between Flashscore LIVE tab and the Flutter app.

Runs in parallel with the main cycle via `asyncio.create_task()` in its **own isolated Playwright instance** (separate temp data dir to prevent browser conflicts).

1. **Extraction**: [fs_live_streamer.py](Modules/Flashscore/fs_live_streamer.py) `live_score_streamer()`
   - Captures live scores, minutes, and statuses every 60s.
   - Uses `extrasaction='ignore'` in CSV writer to handle schema drift.
2. **Delta-Only Push**: Only rows with actual field changes are pushed to Supabase (prevents 0-propagation spam).
3. **Status Propagation**:
   - Marks fixtures as `live` in `predictions.csv` and `schedules.csv`.
   - **2.5hr Rule**: Matches exceeding `kickoff + 2.5h` are auto-transitioned to `finished`.
   - Supports DD.MM.YYYY and ISO date formats for kick-off time parsing.
4. **App Handshake**: Upserts to `live_scores` table via `SyncManager.batch_upsert()`.

---

## High-Velocity Concurrency

**Objective**: Maximize execution throughput via autonomous per-match worker nodes while maintaining absolute data integrity.

1. **Parallel Orchestration**: `Leo.py` uses `BatchProcessor` to spawn multiple `process_match_task` workers in parallel. Match sorting uses `match_time` field for chronological processing.
2. **Integrated Worker Node**: Each worker executes a strict sequential pipeline:
   - **H2H + Standings**: Core match data extraction.
   - **League Enrichment**: Inline navigation to league pages (deduped by `league_id` per cycle).
   - **Search Dict**: JIT metadata enrichment via LLMs (Gemini primary, Grok fallback) with enrichment gate capped at 100 teams max per cycle.
   - **Prediction**: Final rule engine analysis once all data is present.
3. **Shared Locking (CSV_LOCK)**: All persistent data access is protected by a global `asyncio.Lock` in [db_helpers.py](Data/Access/db_helpers.py).
4. **Resiliency**: If one match worker fails, other nodes continue processing. Data is saved incrementally per-match.

---

## Prediction Pipeline (Chapter 1 P1)

1. **Discovery**: [fs_schedule.py](Modules/Flashscore/fs_schedule.py) extracts fixture IDs.
   - Implements 2-tier header expansion retry (JS bulk + Locator fallback) to ensure 100% fixture visibility.
2. **Analysis**: [fs_processor.py](Modules/Flashscore/fs_processor.py) collects H2H and Standings data.
3. **Core Engine**: [rule_engine.py](Core/Intelligence/rule_engine.py) `analyze()`
   - **Rule Logic**: [rule_config.py](Core/Intelligence/rule_config.py) defines the logic constraints.
   - **Poisson Predictor**: [goal_predictor.py](Core/Intelligence/goal_predictor.py) handles O/U and BTTS probabilities.
4. **Rule Engine Registry**: [rule_engine_manager.py](Core/Intelligence/rule_engine_manager.py) supports multiple registered engines with `--rule-engine --list`, `--set-default`, and `--backtest` commands.

---

## Outcome Review & Accuracy

1. **Offline Review**: [outcome_reviewer.py](Data/Access/outcome_reviewer.py) first attempts offline resolution using schedule data.
2. **Browser Fallback**: Unresolved matches with kick-off ≥2h in the past are visited via a headless browser for score extraction. Future/in-progress matches are pre-filtered out.
3. **Accuracy Evaluation**: Supports all markets including team-name-based OR patterns for double chance (e.g., "Arsenal or Liverpool" → accurate if game outcome is not a draw).

---

## Adaptive Learning Intelligence

**Objective**: Continuous evolution of prediction rule weights based on historical accuracy.

1. **Feedback Loop**: [outcome_reviewer.py](Data/Access/outcome_reviewer.py) calls `LearningEngine.update_weights()` after every review batch.
2. **Analysis**: [learning_engine.py](Core/Intelligence/learning_engine.py) matches `predictions.csv` outcomes against the reasoning tags used.
3. **Weight Evolution**:
   - Success triggers **positive reinforcement** for specific weights.
   - Failure triggers **penalty** and weight reduction.
   - Updates `learning_weights.json` (per-league) and syncs to Supabase.
4. **Integration**: `RuleEngine.analyze()` loads these adaptive weights via `LearningEngine.load_weights(region_league)`.

---

## LLM Health Management

**Module**: [llm_health_manager.py](Core/Intelligence/llm_health_manager.py)

- **Multi-Key Rotation**: 25+ Gemini API keys rotated round-robin across 5 models.
- **Dual Model Chains**: DESCENDING (pro→flash) for AIGO/predictions, ASCENDING (lite→flash) for SearchDict throughput.
- **Dead Key Persistence**: Keys returning 403 are permanently excluded via `_dead_keys` set that survives ping cycles.
- **Health Pings**: Samples 3 keys every 15 minutes to validate connectivity without exhausting quota.
- **Grok Optional**: Grok API key is optional; system routes to Gemini-only if unconfigured.

---

## UI Documentation (Flutter)

See [leobookapp/README.md](leobookapp/README.md) for the Liquid Glass design specification and widget architecture.

---

*Last updated: March 1, 2026*
*LeoBook Engineering Team*
