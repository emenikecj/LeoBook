# LeoBook v3.3 Algorithm & Codebase Reference

> **Version**: 3.3 · **Last Updated**: 2026-02-24 · **Architecture**: Concurrent Clean Architecture (Sequential + Parallel Pipeline)

This document maps the **execution flow** of [Leo.py](Leo.py) to specific files and functions.

---

## System Architecture

Leo.py is a **pure orchestrator**. It runs an infinite `while True` loop, splitting the cycle into three phases:

```
Leo.py (Orchestrator) v3.3
├── Phase 1 (Sequential Prerequisite):
│   └── Cloud Sync → Outcome Review → Accuracy report
├── Phase 2 (Concurrent Group):
│   ├── Stream A: Enrichment → Accuracy Generation → Final Sync
│   └── Stream B: Extraction → Adaptive Prediction → Odds → Final Sync → Booking
├── Phase 3 (Sequential Oversight):
│   └── Chief Engineer Oversight → Withdrawal Management
└── Live Streamer: Background Parallel Task (Always-On)
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

## Prediction Pipeline (Chapter 1)

1. **Discovery**: [fs_schedule.py](Modules/Flashscore/fs_schedule.py) extracts fixture IDs.
   - **v3.2 Robustness**: Implements 2-tier header expansion retry (JS bulk + Locator fallback) to ensure 100% fixture visibility.
2. **Analysis**: [fs_processor.py](Modules/Flashscore/fs_processor.py) collects H2H and Standings data.
3. **Core Engine**: [rule_engine.py](Core/Intelligence/rule_engine.py) `analyze()`
   - **Rule Logic**: [rule_config.py](Core/Intelligence/rule_config.py) defines the v3.0 logic constraints.
   - **Poisson Predictor**: [goal_predictor.py](Core/Intelligence/goal_predictor.py) handles O/U and BTTS probabilities.

---

## 5. Adaptive Learning Intelligence

**Objective**: Continuous evolution of prediction rule weights based on historical accuracy.

1. **Feedback Loop**: [outcome_reviewer.py](Data/Access/outcome_reviewer.py) calls `LearningEngine.update_weights()` after every review batch.
2. **Analysis**: [learning_engine.py](Core/Intelligence/learning_engine.py) matches `predictions.csv` outcomes against the reasoning tags used.
3. **Weight Evolution**:
   - Success triggers **positive reinforcement** for specific weights.
   - Failure triggers **penalty** and weight reduction.
   - Updates `learning_weights.json` (per-league) and syncs to Supabase.
4. **Integration**: `RuleEngine.analyze()` loads these adaptive weights via `LearningEngine.load_weights(region_league)`.

---

## 6. UI Documentation (Flutter v3.0)

See [leobookapp/README.md](leobookapp/README.md) for the "Telegram-grade" design specification.
