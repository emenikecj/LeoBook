# LeoBook

**Developer**: Matterialless LLC
**Chief Engineer**: Emenike Chinenye James
**Powered by**: Multi-Key Gemini Rotation (25+ Keys, 5 Models) · xAI Grok API (Optional)
**Architecture**: High-Velocity Concurrent Architecture v4.0 (Per-Match Pipeline + Live Streaming + Adaptive Learning)

---

## What Is LeoBook?

LeoBook is an **autonomous sports prediction and betting system** with two halves:

| Component | Tech | Purpose |
|-----------|------|---------|
| `Leo.py` | Python 3.12 + Playwright | Data extraction, rule-based prediction, odds harvesting, automated bet placement, withdrawal management |
| `leobookapp/` | Flutter/Dart | Cross-platform dashboard with "Telegram-grade" UI density, Liquid Glass aesthetics, and real-time streaming |

Leo.py is a **pure orchestrator** — zero business logic. All logic lives in the modules it imports. It runs in an infinite cycle (default every 6 hours), with a parallel live score streamer running continuously in its own isolated browser session.

For the complete file inventory and step-by-step execution trace, see [LeoBook_Technical_Master_Report.md](LeoBook_Technical_Master_Report.md).

---

## System Architecture (v4.0 Per-Match Pipeline)

```
Leo.py (Orchestrator)
├── Prologue P1 (Sequential Prerequisite):
│   └── Cloud Sync → Outcome Review → Accuracy Report
├── Concurrent Execution:
│   ├── Prologue P2: Accuracy Generation & Final Sync
│   └── Chapter 1→2 Pipeline:
│       ├── Ch1 P1: [Match Worker Node] × MAX_CONCURRENCY
│       │   └── H2H/Standings → League Enrichment → Search Dict → Prediction
│       ├── Ch1 P2: Odds Harvesting & URL Resolution
│       ├── Ch1 P3: Final Sync & Recommendations
│       ├── Ch2 P1: Automated Booking (Football.com)
│       └── Ch2 P2: Funds & Withdrawal Check
├── Chapter 3 (Sequential Finality):
│   └── Chief Engineer Oversight → Backtest → Final Sync
└── Live Streamer: Isolated parallel task — 60s LIVE score streaming + status propagation
```

### Key Subsystems

- **Multi-Key/Multi-Model Gemini Rotation**: Adaptive load balancing across 25+ free-tier keys with 5 models and dual exclusive chains (DESCENDING for AIGO intelligence, ASCENDING for SearchDict throughput). Dead keys (403) are permanently excluded.
- **Dual-LLM Intelligent Routing**: Smart failover between Grok (optional) and Gemini with per-context model selection.
- **Adaptive Learning**: Per-league rule weight evolution via outcome feedback loop.
- **Live Score Streaming**: Isolated Playwright session with delta-only Supabase pushes, 2.5hr auto-finish rule, and schedule/prediction propagation.

### Core Modules

- **`Core/Intelligence/`** — AI engine (rule-based prediction, adaptive learning, AIGO self-healing, LLM health management)
- **`Core/Browser/`** — Playwright automation and data extractors (H2H, standings, league pages)
- **`Core/System/`** — Lifecycle, monitoring, withdrawal checker
- **`Modules/Flashscore/`** — Schedule extraction, match processing, offline reprediction, live score streaming
- **`Modules/FootballCom/`** — Betting platform automation (login, navigation, odds, booking, bet placement)
- **`Data/Access/`** — CSV CRUD, Supabase bi-directional sync, outcome review, accuracy calculation
- **`Scripts/`** — Enrichment pipeline, recommendation engine, search dictionary builder, backtest monitor
- **`leobookapp/`** — Flutter dashboard (Liquid Glass + Proportional Scaling)

### AIGO (AI-Guided Operation) — Self-Healing Framework (v5.4)

Five-phase recovery cascade for every browser interaction (~8-18% reach Phase 3):

0. **Context Discovery** — selector lookup from `knowledge.json`
1. **Reinforcement Learning** — memory-based strategy selection
2. **Visual Analysis** — multi-strategy matching (CSS → XPath → text → fuzzy)
3. **Expert Consultation** — Gemini/Grok API multimodal analysis (screenshot + DOM → primary + backup paths)
4. **Self-Healing & Evolution** — persist AI-discoveries to `knowledge.json` and update `learning_weights.json` via the outcome review loop.

See [AIGO_Learning_Guide.md](AIGO_Learning_Guide.md) for the full pipeline specification.

---

## Supported Betting Markets

1X2 · Double Chance · Draw No Bet · BTTS · Over/Under · Goal Ranges · Correct Score · Clean Sheet · Asian Handicap · Combo Bets · Team O/U

---

## Project Structure

```
LeoBook/
├── Leo.py                  # Orchestrator (dispatch-based CLI)
├── RULEBOOK.md             # Developer rules (MANDATORY reading)
├── Core/
│   ├── Browser/            # Playwright automation + extractors
│   ├── Intelligence/       # AI engine, AIGO, LLM health, selectors, learning
│   ├── System/             # Lifecycle, monitoring, withdrawal
│   └── Utils/              # Constants, utilities
├── Modules/
│   ├── Flashscore/         # Sports data extraction + live streamer
│   └── FootballCom/        # Betting platform automation
│       └── booker/         # Booking sub-module
├── Scripts/                # Pipeline scripts (called by Leo.py)
│   ├── build_search_dict.py  # Team/league LLM enrichment
│   ├── enrich_leagues.py     # League metadata extraction
│   ├── enrich_all_schedules.py # Deep schedule enrichment
│   ├── recommend_bets.py     # Recommendation engine
│   └── backtest_monitor.py   # Backtest integration
├── Data/
│   ├── Access/             # Data access layer + sync
│   ├── Store/              # CSV/JSON data stores (source of truth)
│   └── Supabase/           # Cloud schema + auto-provisioning
├── Config/
│   └── knowledge.json      # CSS selector knowledge base
└── leobookapp/lib/
    ├── core/               # Theme, constants, animations
    ├── data/               # Models, repositories, services
    ├── logic/              # Cubits, state management (flutter_bloc)
    └── presentation/
        ├── screens/        # Pure viewport dispatchers
        └── widgets/
            ├── desktop/    # Desktop-only widgets
            ├── mobile/     # Mobile-only widgets
            └── shared/     # Reusable cross-platform widgets
```

---

## LeoBook App (Flutter)

The app implements a **Telegram-inspired high-density aesthetic** optimized for maximum velocity and visual clarity.

- **Telegram Design Aesthetic** — 80% size reduction for high-density information, glass translucency (60% fill), and micro-radii (14dp).
- **Proportional Scaling System** — Custom `Responsive` utility ensures perfect parity between mobile and web without hardcoded pixel values.
- **Supabase Backend** — Cloud-native data for instant global access via bi-directional sync.
- **Liquid Glass UI** — Premium frosted-glass containers with optimized BackdropFilter performance.
- **Live Data-Driven UI** — Real-time accuracy indicators and team crests dynamically computed from backend match data.
- **4-Tab Match System** — ALL | LIVE | FINISHED | SCHEDULED with automatic 2.5hr status propagation and real-time Supabase streaming.
- **Accuracy Report Cards** — Dynamic per-league accuracy sorted by match count then accuracy percentage.
- **State Management** — `flutter_bloc` / `Cubit` pattern (HomeCubit, UserCubit, SearchCubit).
- **Double Chance Accuracy** — Supports team-name-based OR patterns (e.g., "Arsenal or Liverpool").

---

## Quick Start

### Backend (Leo.py)

```bash
pip install -r requirements.txt
playwright install chromium
cp .env.example .env  # Configure API keys
python Leo.py              # Full cycle (infinite loop)
python Leo.py --prologue    # Run prologue only (P1 + P2)
python Leo.py --prologue --page 1  # Prologue P1 only
python Leo.py --chapter 1   # Run chapter 1 (P1 + P2 + P3)
python Leo.py --chapter 2   # Run chapter 2 (Booking + Withdrawal)
python Leo.py --chapter 3   # Run chapter 3 (Monitoring)
python Leo.py --sync        # Force full cloud sync
python Leo.py --review      # Run outcome review
python Leo.py --accuracy    # Print accuracy report
python Leo.py --recommend   # Generate recommendations
python Leo.py --streamer    # Run live score streamer standalone
python Leo.py --schedule    # Extract schedules
python Leo.py --schedule --all  # Full deep schedule extraction
python Leo.py --schedule --all --date 01.03.2026  # Redo/extract specific day
python Leo.py --chapter 1 --page 1 --refresh     # Re-analyze today (bypass resume)
python Leo.py --enrich      # Manual metadata enrichment
python Leo.py --enrich-leagues  # Parallel league enrichment + search dict
python Leo.py --search-dict # Rebuild team/league search dictionary
python Leo.py --backtest    # Single-pass backtest
python Leo.py --assets      # Sync team and league assets to Supabase
python Leo.py --rule-engine --list  # List registered rule engines
python Leo.py --rule-engine --set-default <name>  # Set default engine
python Leo.py --rule-engine --backtest --from-date 2025-08-01 # Backtest with date
python Leo.py --offline-repredict  # Offline reprediction mode
python Leo.py --help        # See all commands
```

### Frontend (leobookapp)

```bash
cd leobookapp
flutter pub get
flutter run -d chrome  # or: flutter run (mobile)
```

---

## Environment Variables

| Variable | Required | Purpose |
|----------|:--------:|---------|
| `GEMINI_API_KEY` | ✅ | Google Gemini API (comma-separated, 25+ keys for rotation) |
| `GROK_API_KEY` | Optional | xAI Grok API for AIGO Phase 3 expert consultation |
| `SUPABASE_URL` | ✅ | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | ✅ | Supabase service role key (Python backend, full write access) |
| `SUPABASE_ANON_KEY` | ✅ | Supabase anon key (Flutter app, read-only via RLS) |
| `FB_PHONE` | ✅ | Football.com phone number |
| `FB_PASSWORD` | ✅ | Football.com password |
| `LEO_CYCLE_WAIT_HOURS` | Optional | Hours between cycles (default: 6) |
| `HEADLESS_MODE` | Optional | Browser headless mode (default: False) |
| `MAX_CONCURRENCY` | Optional | Parallel match worker limit |

---

## Documentation

| Document | Purpose |
|----------|---------|
| [RULEBOOK.md](RULEBOOK.md) | **MANDATORY** — Developer rules, architecture decisions, coding standards |
| [LeoBook_Technical_Master_Report.md](LeoBook_Technical_Master_Report.md) | Complete file inventory, execution trace, data flow diagrams |
| [leobook_algorithm.md](leobook_algorithm.md) | Algorithm reference — prediction pipeline, learning engine, concurrency |
| [AIGO_Learning_Guide.md](AIGO_Learning_Guide.md) | Self-healing framework specification (5-phase pipeline) |
| [SUPABASE_SETUP.md](SUPABASE_SETUP.md) | Supabase setup, credentials, sync architecture |

---

## Maintenance

- `python Leo.py --sync` — Manual cloud sync
- `python Leo.py --recommend` — Regenerate recommendations
- `python Leo.py --accuracy` — Regenerate accuracy reports
- `python Leo.py --review` — Run outcome review
- `python Leo.py --backtest` — Run backtest check
- `python Leo.py --streamer` — Run live streamer standalone
- `python Leo.py --assets` — Sync team and league assets
- Monitor `Data/Store/audit_log.csv` for real-time event transparency
- Live streamer runs automatically in parallel — check `[Streamer]` logs

---

*Last updated: March 1, 2026*
*Authored by: LeoBook Engineering Team*
