> **Version**: 3.8 · **Last Updated**: 2026-02-27 · **Architecture**: High-Velocity Concurrent Architecture (Shared Locking + Multi-Key/Multi-Model LLM Rotation)

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Project File Map](#2-project-file-map)
3. [Leo.py — Step-by-Step Execution Flow](#3-leopy--step-by-step-execution-flow)
4. [Design & UI/UX (v3.0)](#4-design--uiux-v30)
5. [Data Flow Diagram](#5-data-flow-diagram)

---

## 1. System Overview

LeoBook is a **fully autonomous sports prediction and betting system** comprised of two halves:

| Half | Technology | Purpose |
|------|-----------|---------|
| **Backend (Leo.py)** | Python 3.12 + Playwright | Autonomous data extraction, rule-based prediction, odds harvesting, bet placement, withdrawal management, and system health monitoring |
| **Frontend (leobookapp)** | Flutter/Dart | Elite dashboard with "Telegram-grade" density, liquid glass aesthetics, and proportional scaling |

**Leo.py** is a **pure orchestrator** — it contains zero business logic. All logic lives in the modules it imports. It runs in an infinite loop, executing a cycle every 6h. Starting v3.6, the engine uses **High-Velocity Concurrent Execution** via a per-match sequential pipeline, protected by a global `CSV_LOCK` for storage integrity.

---

## 2. Project File Map

### 2.1 Root Files

| File | Function | Called by Leo.py? |
|------|----------|:-:|
| `Leo.py` | Central orchestrator — runs the entire system in a loop | **Entrypoint** |
| `.env` | API keys (Grok, Supabase), config (`LEO_CYCLE_WAIT_HOURS`, etc.) | ✅ via `dotenv` |
| `AIGO_Learning_Guide.md` | Documentation for the AIGO (AI Operator) subsystem | — |
| `leobook_algorithm.md` | Prediction algorithm whitepaper (v3.6) | — |
| `SUPABASE_SETUP.md` | Supabase setup instructions | — |

---

### 2.2 `Modules/` — Domain Logic Updates

| File | Function | Called by Leo.py? |
|------|----------|:-:|
| `fs_live_streamer.py` | **v2.1 Revision**: Parallel live score streaming with `extrasaction='ignore'` CSV robustness and 60s sync status propagation | ✅ (Parallel Task) |

---

### 2.3 `leobookapp/` — Flutter Architecture (v3.0)

The v3.0 rebuild implements a **Constraints-Based Design** system for uniform scaling.

| Directory | Feature | Purpose |
| :--- | :--- | :--- |
| `lib/core/constants/` | **`responsive_constants.dart`** | Central `Responsive.sp()` utility for dynamic font and spacing scaling |
| `lib/presentation/widgets/desktop/` | **Desktop-Only** | `DesktopHomeContent`, `DesktopHeader`, `NavigationSidebar` |
| `lib/presentation/widgets/mobile/` | **Mobile-Only** | `MobileHomeContent` — full mobile home layout with tabs |
| `lib/presentation/widgets/shared/` | **Reusable** | `MatchCard`, `FeaturedCarousel`, `NewsFeed`, `RecommendationCard`, `CategoryBar`, `LeoTab`, etc. |
| `lib/presentation/widgets/shared/league_tabs/` | **League Tabs** | Overview, Fixtures, Predictions, Stats tabs |
| `lib/presentation/screens/` | **Dispatchers** | Pure viewport dispatchers — render desktop or mobile widget tree |

---

## 3. Leo.py — Step-by-Step Execution Flow

Leo.py orchestrates 3 main phases sequentially:

### Startup Flow
1. **Singleton Check**: Ensure only one instance runs.
2. **CSV Init**: Create local databases if missing.
3. **Browser Engine**: Launch Playwright context.

### Per-Cycle Logic (6h Cycle) — Per-Match Pipeline (v3.6)

Leo.py splits the cycle into three phases: Sequential Prep, Parallel Match Pipeline, and Sequential Finality.

#### Phase 1: Sequential Preparation (Prerequisite)
| # | Phase | Module Called | Action |
|---|-------|-------------|--------|
| 1 | **Prologue P1** | `SyncManager` | Bi-directional Supabase handshake (Sync on Startup). |
| 2 | **Prologue P1** | `outcome_reviewer` | Match score matching for results + Accuracy Report. |

#### Phase 2: Parallel Match Pipeline (High-Velocity Execution)
| Execution Stream | Phase | Process Unit | Action | Concurrency |
|:--- | :--- | :--- | :--- | :--- |
| Parallel Node | **Match Processor** | `process_match_task` | Sequential: H2H → Standings → Metadata → League Enrichment → Search Dict → Predict. | `MAX_CONCURRENCY` |

#### Phase 3: Sequential Finality (Oversight)
| # | Phase | Module Called | Action |
|---|-------|-------------|--------|
| 1 | **Chapter 3** | `monitoring.py` | Health check, oversight reporting, and withdrawal management. |

---

## 4. Design & UI/UX (v3.0)

### 4.1 Proportional Scaling
Standardized on a **375dp reference** for mobile and **1440dp** for desktop. 
- `Responsive.sp(context, 16)` returns proportional results based on `MediaQuery.sizeOf(context).width`.
- Prevents UI overflows across 100% of tested devices.

### 4.2 Liquid Glass Aesthetic
- **Fill Opacity**: 60% translucency for depth.
- **Blur Radius**: 16 sigma BackdropFilter.
- **Micro-Radii**: 14dp border radius for a sharp, dense look.

---

## 5. Data Flow Diagram

```mermaid
flowchart LR
    subgraph SOURCES ["External Sources"]
        FS[("Flashscore.com<br/>Match Data")]
        FB[("Football.com<br/>Betting Platform")]
        LLM[("Gemini Multi-Key/Model Rotation<br/>14 Keys · 5 Models · dual chains")]
    end

    subgraph LEO ["Leo.py Orchestrator"]
        direction TB
        EXTRACT["Extract<br/>(Flashscore)"]
        PREDICT["Predict<br/>(Rule Engine)"]
        HARVEST["Harvest Odds<br/>(Football.com)"]
        BOOK["Place Bets<br/>(Football.com)"]
        AIGO["🛡️ AIGO<br/>(Self-Healing)"]
        MONITOR["Monitor<br/>(Health Check)"]
    end

    subgraph DATA ["Data Layer"]
        CSV[("Local CSVs<br/>predictions.csv<br/>schedules.csv")]
        LOCK["🔒 CSV_LOCK<br/>(Shared Locking)"]
        LW[("learning_weights.json<br/>Adaptive Rule Weights")]
        KJ[("knowledge.json<br/>Selector Knowledge Base")]
        SB[("Supabase<br/>Cloud Database")]
    end

    subgraph APP ["Flutter App"]
        MOBILE["📱 LeoBook App<br/>(v3.0)"]
    end

    FS --> EXTRACT --> CSV
    CSV <--> LOCK
    CSV --> PREDICT --> CSV
    CSV --> HARVEST
    FB --> HARVEST --> CSV
    CSV --> BOOK --> FB
    HARVEST -.->|"selector failure logs"| AIGO
    BOOK -.->|"UI failure logs"| AIGO
    AIGO --> LLM
    AIGO -->|"persist selector & log_selector_failure"| KJ
    CSV <--> SB
    LW <--> SB
    SB --> MOBILE
    MONITOR --> CSV
    CSV -.->|"compute adaptive accuracy"| MOBILE
    CSV -.->|"analyze outcomes"| LW
```

---
*Generated by Antigravity AI · v3.8 Intelligence Update*
