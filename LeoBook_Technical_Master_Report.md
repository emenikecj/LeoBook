# LeoBook — Technical Master Report

> **Version**: 3.0 · **Last Updated**: 2026-02-18 · **Architecture**: Clean Architecture (Orchestrator → Module → Data)

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
| **Backend (Leo.py)** | Python 3.12 + Playwright | Autonomous data extraction, AI prediction, odds harvesting, bet placement, withdrawal management, and system health monitoring |
| **Frontend (leobookapp)** | Flutter/Dart | Elite dashboard with "Telegram-grade" density, liquid glass aesthetics, and proportional scaling |

**Leo.py** is a **pure orchestrator** — it contains zero business logic. All logic lives in the modules it imports. It runs in an infinite loop, executing a cycle every 6h.

---

## 2. Project File Map

### 2.1 Root Files

| File | Function | Called by Leo.py? |
|------|----------|:-:|
| `Leo.py` | Central orchestrator — runs the entire system in a loop | **Entrypoint** |
| `.env` | API keys (Grok, Supabase), config (`LEO_CYCLE_WAIT_HOURS`, etc.) | ✅ via `dotenv` |
| `AIGO_Learning_Guide.md` | Documentation for the AIGO (AI Operator) subsystem | — |
| `leobook_algorithm.md` | Prediction algorithm whitepaper (v3.0) | — |
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
| `lib/presentation/widgets/` | **High Density** | 80% reduction in UI element sizes for professional "Telegram-grade" information density |
| `lib/presentation/widgets/responsive/` | **Adaptive Layouts** | Viewport-aware widgets (`CategoryBar`, `NavigationSidebar`) that scale proportionally |

---

## 3. Leo.py — Step-by-Step Execution Flow

Leo.py orchestrates 3 main chapters sequentially:

### Startup Flow
1. **Singleton Check**: Ensure only one instance runs.
2. **CSV Init**: Create local databases if missing.
3. **Browser Engine**: Launch Playwright context.

### Per-Cycle Logic (6h Cycle)

| # | Phase | Module Called | Action |
|---|-------|-------------|--------|
| 1 | **Prologue** | `SyncManager` | Bi-directional Supabase handshake. |
| 2 | **Prologue** | `outcome_reviewer` | Parallel Flashscore score matching for results. |
| 3 | **Prologue** | `enrich_all_schedules` | Visit URLs to extract team crests, IDs, and standings. |
| 4 | **Chapter 1** | `manager.py` | Scrape today's fixtures and run AI predictions. |
| 5 | **Chapter 1** | `fb_manager.py` | Fuzzy-match to Football.com and extract booking codes. |
| 6 | **Chapter 1** | `recommend_bets` | Score predictions and save `recommended.json`. |
| 7 | **Chapter 2** | `placement.py` | Inject codes and place bets with Kelly staking. |
| 8 | **Chapter 3** | `monitoring.py` | Health check and oversight reporting. |

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
        GROK[("Grok API<br/>LLM Intelligence")]
    end

    subgraph LEO ["Leo.py Orchestrator"]
        direction TB
        EXTRACT["Extract<br/>(Flashscore)"]
        PREDICT["Predict<br/>(Intelligence)"]
        HARVEST["Harvest Odds<br/>(Football.com)"]
        BOOK["Place Bets<br/>(Football.com)"]
        AIGO["🛡️ AIGO<br/>(Self-Healing)"]
        MONITOR["Monitor<br/>(Health Check)"]
    end

    subgraph DATA ["Data Layer"]
        CSV[("Local CSVs<br/>predictions.csv<br/>schedules.csv")]
        KJ[("knowledge.json<br/>Selector Knowledge Base")]
        SB[("Supabase<br/>Cloud Database")]
    end

    subgraph APP ["Flutter App"]
        MOBILE["📱 LeoBook App<br/>(v3.0)"]
    end

    FS --> EXTRACT --> CSV
    CSV --> PREDICT --> CSV
    CSV --> HARVEST
    FB --> HARVEST --> CSV
    CSV --> BOOK --> FB
    GROK --> PREDICT
    HARVEST -.->|"selector failure"| AIGO
    BOOK -.->|"UI failure"| AIGO
    AIGO --> GROK
    AIGO -->|"persist selector"| KJ
    CSV <--> SB
    SB --> MOBILE
    MONITOR --> CSV
```

---
*Generated by Antigravity AI · v3.0 Dashboard Update*
