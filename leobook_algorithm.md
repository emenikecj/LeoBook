# LeoBook v3.0 Algorithm & Codebase Reference

> **Version**: 3.0 · **Last Updated**: 2026-02-18 · **Architecture**: Clean Architecture (Orchestrator → Module → Data)

This document maps the **execution flow** of [Leo.py](Leo.py) to specific files and functions.

---

## System Architecture

Leo.py is a **pure orchestrator**. It runs an infinite `while True` loop, executing 4 phases sequentially every 6h.

```
Leo.py (Orchestrator)
├── Prologue: Cloud Sync → Outcome Review → Enrichment → Accuracy → Final Sync
├── Chapter 1: Flashscore Extraction → AI Prediction → Odds Harvesting → Recommendations
├── Chapter 2: Automated Bet Placement → Withdrawal Management
├── Chapter 3: Chief Engineer Oversight & Health Check
└── Live Streamer: Parallel 60s LIVE score streaming (v2.1 fix)
```

---

## Live Streamer (Parallel v2.1)

**Objective**: Absolute real-time parity between Flashscore LIVE tab and the Flutter app.

Runs in parallel with the main cycle via `asyncio.create_task()`.

1. **Extraction**: [fs_live_streamer.py](Modules/Flashscore/fs_live_streamer.py) `live_score_streamer()`
   - Captures live scores, minutes, and statuses every 60s.
   - **v2.1 Robustness Fix**: Uses `extrasaction='ignore'` in CSV writer to handle schema drift.
2. **Status Propagation**: 
   - Marks fixtures as `live` in `predictions.csv`.
   - Detects `finished` matches (kickoff + 2.5h) even if the main cycle is sleeping.
   - Computes real-time `outcome_correct` for immediate app updates.
3. **App Handshake**: Upserts to `live_scores` table in Supabase via `SyncManager.batch_upsert()`.

---

## AI Prediction Pipeline (Chapter 1)

1. **Discovery**: [fs_schedule.py](Modules/Flashscore/fs_schedule.py) extracts fixture IDs.
2. **Analysis**: [fs_processor.py](Modules/Flashscore/fs_processor.py) collects H2H and Standings data.
3. **Core Engine**: [intelligence.py](Core/Intelligence/intelligence.py) `make_prediction()`
   - **ML Model**: [ml_model.py](Core/Intelligence/ml_model.py) matches patterns against 10k+ historical matches.
   - **Poisson Predictor**: [goal_predictor.py](Core/Intelligence/goal_predictor.py) handles O/U and BTTS probabilities.
   - **Rule Engine**: [rule_engine.py](Core/Intelligence/rule_engine.py) filters predictions against v3.0 logic constraints.

---

## UI Documentation (Flutter v3.0)

See [leobookapp/README.md](leobookapp/README.md) for the "Telegram-grade" design specification.
