# LeoBook

**Developer**: Matterialless LLC
**Chief Engineer**: Emenike Chinenye James
**Powered by**: Grok 4.1 & Gemini 3
**Architecture**: Concurrent Clean Architecture v3.3 (Sequential + Parallel Pipeline)

---

## What Is LeoBook?

LeoBook is an **autonomous sports prediction and betting system** with two halves:

| Component | Tech | Purpose |
|-----------|------|---------|
| `Leo.py` | Python 3.12 + Playwright | Data extraction, rule-based prediction, odds harvesting, automated bet placement, withdrawal management |
| `leobookapp/` | Flutter/Dart | Elite, cross-platform dashboard with "Telegram-grade" UI density and real-time streaming |

Leo.py is a **pure orchestrator** — zero business logic. All logic lives in the modules it imports. It runs in an infinite cycle (default every 6 hours).

For the complete file inventory and step-by-step execution trace, see [LeoBook_Technical_Master_Report.md](LeoBook_Technical_Master_Report.md).

---

## System Architecture (v3.2 Concurrent)

```
Leo.py (Orchestrator)
├── Phase 1 (Sequential): Cloud Sync → Outcome Review → Accuracy Report
├── Phase 2 (Concurrent/Gather):
│   ├── Stream A: Enrichment → Final Prologue Sync
│   └── Stream B: Extraction → Adaptive Prediction → Odds Harvesting → Booking
├── Phase 3 (Sequential): Chief Engineer Oversight & Withdrawal Management
└── Live Streamer: Background 60s LIVE score streaming → status propagation
```

### Key Innovations (v3.2)
- **Concurrent Pipeline**: Prologue enrichment runs alongside Chapter 1 predictions, reducing cycle time by ~30%.
- **First-Principles Cleanup**: Stripped 12+ dead files and unified popup/selector architectures for a minimalist, ultra-fast codebase.
- **End-to-End Resumability**: Every step (Harvesting, Booking, Enrichment) uses persistent status checks to skip already-processed items on restart.
- **Adaptive Learning Feedback**: Rule weights and confidence calibration now evolve after every outcome review, stored in `learning_weights.json` and synced to the cloud.
- **Robust Scrapers**: 2-tier header expansion retry logic (JS + Locator) in Flashscore scrapers.

### Core Modules

- **`Core/Intelligence/`** — Intelligence engine (rule-based prediction engine, rule config, AIGO self-healing)
- **`Core/Browser/`** — Playwright automation and data extractors (H2H, standings, league pages)
- **`Core/System/`** — Lifecycle, monitoring, withdrawal checker
- **`Modules/Flashscore/`** — Schedule extraction, match processing, offline reprediction, **live score streaming (v2.1 fix)**
- **`Modules/FootballCom/`** — Betting platform automation (login, navigation, odds, booking, bet placement)
- **`Data/Access/`** — CSV CRUD, Supabase sync, outcome review, accuracy calculation
- **`Scripts/`** — Enrichment pipeline, recommendation engine, maintenance utilities
- **`leobookapp/`** — **UI v3.0 (Liquid Glass + Proportional Scaling)**

### AIGO (AI-Guided Operation) — Self-Healing Framework (v5.0)

Five-phase recovery cascade for every browser interaction (~8-18% reach Phase 3):

0. **Context Discovery** — selector lookup from `knowledge.json`
1. **Reinforcement Learning** — memory-based strategy selection
2. **Visual Analysis** — multi-strategy matching (CSS → XPath → text → fuzzy)
3. **Expert Consultation** — Grok API multimodal analysis (screenshot + DOM → primary + backup paths)
4. **Self-Healing & Evolution** — persist AI-discoveries to `knowledge.json` and update `learning_weights.json` via the outcome review loop.

See [AIGO_Learning_Guide.md](AIGO_Learning_Guide.md) for the full pipeline specification.

---

## Supported Betting Markets

1X2 · Double Chance · Draw No Bet · BTTS · Over/Under · Goal Ranges · Correct Score · Clean Sheet · Asian Handicap · Combo Bets · Team O/U

---

## Project Structure

```
LeoBook/
├── Leo.py                  # Orchestrator v3.0 (dispatch-based CLI)
├── RULEBOOK.md             # Developer rules (MANDATORY reading)
├── Core/
│   ├── Browser/            # Playwright automation + extractors
│   ├── Intelligence/       # AI engine, AIGO, selectors
│   ├── System/             # Lifecycle, monitoring, withdrawal
│   └── Utils/              # Constants, utilities
├── Modules/
│   ├── Flashscore/         # Sports data extraction + live streamer
│   └── FootballCom/        # Betting platform automation
├── Scripts/                # Pipeline scripts (called by Leo.py)
│   └── archive/            # Diagnostic/one-time scripts
├── Data/
│   ├── Access/             # Data access layer + sync
│   ├── Store/              # CSV/JSON data stores
│   └── Supabase/           # Cloud schema
├── Config/
│   └── knowledge.json      # CSS selector knowledge base
└── leobookapp/lib/
    ├── core/               # Theme, constants, animations
    ├── data/               # Models, repositories, services
    ├── logic/              # Cubits, state management
    └── presentation/
        ├── screens/        # Pure viewport dispatchers
        └── widgets/
            ├── desktop/    # Desktop-only widgets
            ├── mobile/     # Mobile-only widgets
            └── shared/     # Reusable cross-platform widgets
```

---

## LeoBook App (Flutter v3.0)

The v3.0 rebuild introduces a **Telegram-inspired high-density aesthetic** optimized for maximum velocity and visual clarity.

- **Telegram Design Aesthetic** — 80% size reduction for high-density information, increased glass translucency (60% fill), and micro-radii (14dp).
- **Proportional Scaling System** — Custom `Responsive` utility ensures perfect parity between mobile and web without hardcoded pixel values.
- **Supabase Backend** — Cloud-native data for instant global access.
- **Liquid Glass UI** — Premium frosted-glass containers with optimized BackdropFilter performance.
- **4-Tab Match System** — ALL | LIVE | FINISHED | SCHEDULED with automatic 2.5hr status propagation from live streamer.
- **Live Accuracy Tags** — Real-time performance indicators fed by the backend review pipeline.

---

## Quick Start

### Backend (Leo.py)

```bash
pip install -r requirements.txt
playwright install chromium
cp .env.example .env  # Configure API keys
python Leo.py              # Full cycle
python Leo.py --prologue    # Run prologue only
python Leo.py --chapter 1   # Run chapter 1 only
python Leo.py --chapter 2 --page 1 # Automated Booking only
python Leo.py --chapter 2 --page 2 # Withdrawal Check only
python Leo.py --sync        # Sync only
python Leo.py --help        # See all 20+ commands
```


### Frontend (leobookapp)

```bash
cd leobookapp
flutter pub get
flutter run -d chrome  # or: flutter run (mobile)
```

---

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `GROK_API_KEY` | xAI Grok API for AIGO (Autonomous Intelligence Guided Operation) & Search Dictionary building |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Supabase service role key (Python backend, full write access) |
| `SUPABASE_ANON_KEY` | Supabase anon key (Flutter app, read-only via RLS) |
| `LLM_API_URL` | Local Leo AI server fallback (optional) |
| `LEO_CYCLE_WAIT_HOURS` | Hours between cycles (default: 6) |

---

## Documentation

| Document | Purpose |
|----------|---------|
| [RULEBOOK.md](RULEBOOK.md) | **MANDATORY** — Developer rules, architecture decisions, coding standards |
| [LeoBook_Technical_Master_Report.md](LeoBook_Technical_Master_Report.md) | Complete file inventory, execution trace, data flow diagrams |
| [leobook_algorithm.md](leobook_algorithm.md) | Algorithm reference — every function call mapped to its module |
| [AIGO_Learning_Guide.md](AIGO_Learning_Guide.md) | Self-healing framework specification (5-phase pipeline) |
| [SUPABASE_SETUP.md](SUPABASE_SETUP.md) | Supabase setup, credentials, Flutter config |

---

## Maintenance

- `python Leo.py --sync` — Manual cloud sync
- `python Leo.py --recommend` — Regenerate recommendations
- `python Leo.py --accuracy` — Regenerate accuracy reports
- `python Leo.py --review` — Run outcome review
- `python Leo.py --backtest` — Run backtest check
- Monitor `Data/Store/audit_log.csv` for real-time event transparency
- Live streamer runs automatically in parallel — check `[Streamer]` logs
