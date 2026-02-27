# LeoBook Developer RuleBook v3.6

> **This document is LAW.** Every developer and AI agent working on LeoBook MUST follow these rules without exception. Violations will break the system.

---

## 1. First Principles

Before writing ANY code, ask in this exact order:

1. **Question** — Is this feature/change actually needed? What problem does it solve?
2. **Delete** — Can existing code be removed instead of adding more?
3. **Simplify** — What is the simplest possible implementation?
4. **Accelerate** — Can this run concurrently or be parallelized?
5. **Automate** — Can Leo.py orchestrate this without human intervention?

---

## 2. Backend Architecture (Python)

### 2.1 Leo.py Is the Single Entry Point

- **`Leo.py` is a PURE ORCHESTRATOR** — it contains ZERO business logic or function definitions beyond page-level dispatchers.
- ALL logic lives in the modules Leo.py calls.
- Every script MUST be callable via `Leo.py` CLI flags. No standalone scripts in production.
- New pipeline steps get a `--flag` in `lifecycle.py` `parse_args()` and a dispatcher in `Leo.py`.

### 2.2 Every Page Function MUST Sync

Every page function (`run_prologue_p1`, `run_chapter_1_p2`, etc.) MUST call `await run_full_sync()` before returning. No exceptions. Data parity between local CSVs and Supabase must be maintained at every step.

### 2.3 Chapter Structure

```
Prologue P1: Cloud Handshake & Review    → sync_on_startup + review
Prologue P2: Final Sync & Cleanup        → accuracy + sync
Chapter 1 (Per-Match Pipeline):
    1. Extraction (Match page)            → H2H + Standings
    2. Enrichment (League page)           → Metadata + Match URLs + Teams
    3. Search Dict (LLM)                  → Search terms + Abbreviations
    4. Prediction (Adaptive)              → Probability + Save
Chapter 2: Booking & Withdrawal           → book + withdraw + sync
Chapter 3: Monitoring & Oversight        → monitor + backtest + sync
```

### 2.4 File Headers (MANDATORY)

Every Python file MUST have this header format:

```python
# filename.py: One-line description of what this file does.
# Part of LeoBook <Component> — <Sub-component>
#
# Functions: func1(), func2(), func3()
# Called by: Leo.py (Chapter X Page Y) | other_module.py
```

### 2.5 No Dead Code

- No commented-out code blocks
- No unused imports
- No functions that are never called
- Run `python -c "from <module> import <func>; print('[OK]')"` to verify

### 2.6 Concurrency Rules

- **Per-Match Pipeline**: Match processing is the primary unit of concurrency. Use `BatchProcessor` to spawn autonomous worker nodes.
- **Max Concurrency**: The number of parallel match workers is strictly limited by `MAX_CONCURRENCY` in `.env`.
- **Sequential Integrity**: Inside each worker, steps (Extraction → Enrichment → Search Dict → Prediction) must remain SEQUENTIAL to ensure data completeness.
- **Shared Locking**: Every disk write to `Data/Store/` MUST be wrapped in `async with CSV_LOCK:`.
- Never use `time.sleep()` in async code — use `await asyncio.sleep()`.
- **Adaptive Feedback:** The `LearningEngine` must update weights AFTER `outcome_reviewer` completes a batch.

---

## 3. Frontend Architecture (Flutter/Dart)

### 3.1 Widget Folder Structure (STRICT)

```
lib/presentation/widgets/
├── desktop/      ← Desktop-ONLY widgets (desktop_header, navigation_sidebar, etc.)
├── mobile/       ← Mobile-ONLY widgets (mobile_home_content, etc.)
└── shared/       ← Reusable widgets used by BOTH layouts
    └── league_tabs/  ← League-specific tab widgets
```

**Rules:**
- A widget goes in `desktop/` if it's ONLY rendered on desktop viewports
- A widget goes in `mobile/` if it's ONLY rendered on mobile viewports
- A widget goes in `shared/` if it's used by BOTH desktop AND mobile layouts
- **NEVER** put a widget in the root `widgets/` folder — it must be in a subfolder

### 3.2 Screens Are Pure Dispatchers

Screen files (`home_screen.dart`, etc.) should use `LayoutBuilder` or `Responsive.isDesktop()` to dispatch to the appropriate platform widget. They should NOT contain inline layout code for either platform.

**Pattern:**
```dart
@override
Widget build(BuildContext context) {
  if (Responsive.isDesktop(context)) {
    return DesktopHomeContent(state: state);
  }
  return MobileHomeContent(state: state);
}
```

### 3.3 Constraints-Based Design (NO HARDCODED VALUES)

**The single most important rule:** Never use fixed `double` values (like `width: 300`) for layout-critical elements.

Use these widgets instead:
- `LayoutBuilder` — adapt widget trees based on parent `maxWidth`
- `Flexible` / `Expanded` — prevent overflow in `Row` / `Column`
- `FractionallySizedBox` — size as percentage of parent
- `AspectRatio` — maintain proportions without fixed dimensions
- `Responsive.sp(context, value)` — scaled spacing/font sizes

**Breakpoint system:**
```dart
static bool isDesktop(BuildContext context) => MediaQuery.sizeOf(context).width >= 900;
static bool isTablet(BuildContext context) => MediaQuery.sizeOf(context).width >= 600;
```

### 3.4 File Headers (MANDATORY)

Every Dart file MUST have this header format using `//` (NOT `///`):

```dart
// filename.dart: One-line description.
// Part of LeoBook App — <Component>
//
// Classes: WidgetName, ClassName
```

> **CRITICAL:** Use `//` not `///` for file-level headers. Triple-slash `///` creates dangling library doc comments and triggers analyzer warnings.

### 3.5 State Management

- Use `flutter_bloc` / `Cubit` for app-level state
- `StatefulWidget` ONLY when the widget owns internal state (animations, controllers, tabs)
- `StatelessWidget` when the widget is a pure function of its inputs
- **NEVER use `setState()` for business logic** — only for local UI state (animations, tab index)

### 3.6 Import Style

- Use `package:` imports for cross-boundary references (e.g., from screens to models)
- Use relative imports (`../`) ONLY for same-component references (e.g., widget to sibling widget)
- Count `../` depth carefully when files move. After every folder restructure, run `flutter analyze`

---

## 4. Data Layer

### 4.1 CSV Is Source of Truth (Offline-First)

Local CSVs in `Data/Store/` are the primary data source. Supabase is the cloud sync target.

- All operations read/write CSVs first
- `run_full_sync()` pushes changes to Supabase
- Conflict resolution: **Latest Wins** (based on `last_updated` timestamp)

### 4.2 Table Config Is Centralized

All table definitions live in `sync_manager.py` `TABLE_CONFIG`. To add a new table:
1. Add entry to `TABLE_CONFIG`
2. Add CSV headers to `db_helpers.py` `files_and_headers`
   - **TEAMS**: `['team_id', 'team_name', 'league_ids', 'team_crest', 'team_url', 'last_updated', 'country', 'city', 'stadium', 'other_names', 'abbreviations', 'search_terms']`
   - **REGION_LEAGUE**: `['league_id', 'region', 'region_flag', 'region_url', 'league', 'league_crest', 'league_url', 'date_updated', 'last_updated', 'other_names', 'abbreviations', 'search_terms']`
3. Create Supabase table with matching schema
4. Run `python Leo.py --sync` to verify

### 4.3 Unextracted Data MUST Be "Unknown"

Any CSV cell or database column whose value was **not extracted** during scraping MUST contain the string `Unknown` — **never** an empty string, `null`, `None`, or blank. This applies to all extractors (schedule, H2H, standings, enrichment) and all persistence layers.

- Scores (`home_score`, `away_score`) are exempt — they are legitimately empty before a match starts.
- `match_status` defaults to `scheduled` when no status is detected.
- Timestamps (`last_updated`, `date_updated`) use the current ISO timestamp.

### 4.4 Incremental Persistence

Every long-running enrichment or scraping task MUST implement **incremental disk writes**. Data should be persisted to local CSVs/Supabase after EACH item is processed. Do not wait for the entire batch to complete.

### 4.6 Concurrency & Shared Locking (v3.5)

To prevent data corruption during parallel execution, all shared CSV access MUST follow the **Shared Locking** protocol:
- **`CSV_LOCK`**: Use the global `asyncio.Lock` from `db_helpers.py`.
- **Block-Level Locking**: Wrap every read-modify-write block in `async with CSV_LOCK:`.
- **Atomic Operations**: For simple reads or writes, use the `async_read_csv` and `async_write_csv` helpers to ensure atomic access.
- **Deadlock Avoidance**: Never acquire multiple locks; stick to the single global `CSV_LOCK` for all `Data/Store/` persistence.

### 4.7 Live Status Restriction (2.5hr Rule)
Only matches within a **2.5-hour window from the scheduled match time** can hold a `LIVE` status. Any match exceeding this threshold MUST be transitioned to `finished` (if no other terminal status is present) by the `fs_live_streamer.py` propagation logic. This ensures UI accuracy and prevents stale live bages.

---

## 5. Deployment & Verification

### 5.1 Before Every Commit

```bash
# Python
python Leo.py --help                    # Verify CLI
python -c "from Leo import main; print('[OK]')"  # Verify imports

# Flutter
flutter analyze                         # Must return 0 issues
flutter run -d chrome                   # Visual smoke test
```

### 5.2 Terminal Commands

- Run ALL commands in the visible terminal — NEVER background or daemonize
- Show full output — no silent failures
- If something needs interaction, pause and ask

### 5.3 No Standalone Scripts

Every script MUST be callable through `Leo.py`. If you write a new utility:
1. Add it to `lifecycle.py` `parse_args()`
2. Add a dispatcher in `Leo.py` `run_utility()` or `dispatch()`
3. Test with `python Leo.py --your-flag`

---

## 6. Folder Structure Summary

```
LeoBook/
├── Leo.py                 ← Single entry point (orchestrator only)
├── Core/
│   ├── System/            ← Lifecycle, monitoring, withdrawal
│   ├── Intelligence/      ← AI engine, rule engine, LLM, selectors
│   ├── Browser/           ← Playwright helpers, extractors
│   └── Utils/             ← Constants, utilities
├── Data/
│   ├── Access/            ← DB helpers, sync, CSV ops, review
│   ├── Store/             ← CSV files (source of truth)
│   └── Supabase/          ← Migration scripts (archived)
├── Modules/
│   ├── Flashscore/        ← Scraping, analysis, live streamer
│   └── FootballCom/       ← Odds, booking, withdrawal
│       └── booker/        ← Booking sub-module
├── Scripts/               ← Pipeline scripts (called by Leo.py)
│   └── archive/           ← Diagnostic/one-time scripts
└── leobookapp/lib/
    ├── core/              ← Theme, constants, animations, widgets
    ├── data/              ← Models, repositories, services
    ├── logic/             ← Cubits, state management
    └── presentation/
        ├── screens/       ← Pure dispatchers (desktop/mobile)
        └── widgets/
            ├── desktop/   ← Desktop-only widgets
            ├── mobile/    ← Mobile-only widgets
            └── shared/    ← Cross-platform reusable widgets
```

---

## 7. Golden Rules

1. **Leo.py calls everything.** No exceptions.
2. **Every page syncs.** Data parity is non-negotiable.
3. **No hardcoded dimensions.** Use constraints-based design.
4. **Screens dispatch, widgets render.** Clean separation.
5. **Delete before adding.** Question every line of code.
6. **`flutter analyze` must return 0.** Always. Before every commit.
7. **Headers on every file.** No exceptions.
8. **Visible terminal only.** No hidden processes.

---

## 8. Flutter Design Specification — Liquid Glass

### 8.1 Font: Google Fonts — Lexend

| Level | Size | Weight | Spacing | Color |
|-------|------|--------|---------|-------|
| `displayLarge` | 22px | w700 (Bold) | -1.0 | `#FFFFFF` |
| `titleLarge` | 15px | w600 (SemiBold) | -0.3 | `#FFFFFF` |
| `titleMedium` | 13px | w600 | default | `#F1F5F9` |
| `bodyLarge` | 13px | w400 | default | `#F1F5F9` (1.5 line height) |
| `bodyMedium` | 11px | w400 | default | `#64748B` (1.5 line height) |
| `bodySmall` | 10px | w400 | default | `#64748B` |
| `labelLarge` | 9px | w700 | 0.8 | `#64748B` |

### 8.2 Color Palette

#### Brand & Primary
| Token | Hex | Usage |
|-------|-----|-------|
| `primary` / `electricBlue` | `#137FEC` | Buttons, active indicators, tab accents |

#### Backgrounds
| Token | Hex | Usage |
|-------|-----|-------|
| `backgroundDark` | `#101922` | Main scaffold (dark mode) |
| `backgroundLight` | `#F6F7F8` | Main scaffold (light mode) |
| `surfaceDark` | `#182430` | Elevated surfaces |
| `bgGradientStart` | `#0D1620` | Background gradient top |
| `bgGradientEnd` | `#162232` | Background gradient bottom |

#### Desktop-Specific
| Token | Hex | Usage |
|-------|-----|-------|
| `desktopSidebarBg` | `#0D141C` | Navigation sidebar |
| `desktopHeaderBg` | `#0F1720` | Top header bar |
| `desktopSearchFill` | `#141F2B` | Search input fill |

#### Glass Tokens (60% translucency default)
| Token | Hex | Alpha |
|-------|-----|-------|
| `glassDark` | `#1A2332` | 80% (`0xCC`) theme constant, **60% (`0x99`) GlassContainer default** |
| `glassLight` | `#FFFFFF` | 80% constant, 60% container |
| `glassBorderDark` | `#FFFFFF` | 10% (`0x1A`) |
| `glassBorderLight` | `#FFFFFF` | 20% (`0x33`) |
| `innerGlowDark` | `#FFFFFF` | 3% (`0x08`) |

#### Semantic Colors
| Token | Hex | Usage |
|-------|-----|-------|
| `liveRed` | `#FF3B30` | Live match badges |
| `successGreen` | `#34C759` | Win indicators, positive states |
| `accentBlue` | `#00D2FF` | Secondary accent |
| `warning` | `#EAB308` | Caution states |
| `aiPurple` | `#8B5CF6` | AI/ML feature accents |
| `accentYellow` | `#FFCC00` | Highlight accents |

#### Text
| Token | Hex | Usage |
|-------|-----|-------|
| `textDark` | `#0F172A` | Dark-on-light text |
| `textLight` | `#F1F5F9` | Light-on-dark text |
| `textGrey` | `#64748B` | Secondary/muted text |
| `textHint` | `#475569` | Placeholder text |

### 8.3 Glass System

| Property | Values |
|----------|--------|
| **Blur** | Full: `24σ` · Medium: `16σ` · Light: `8σ` · None: `0` (performance toggle) |
| **Opacity** | Full: `75%` · Medium: `55%` · Light: `35%` |
| **Border Radius** | Large: `28dp` · Default: `20dp` · Small: `12dp` |
| **Border Width** | `0.5px` default, `1.0px` for emphasis |
| **Card Radius** | `14dp` (Material card theme) |

#### GlassContainer Interactions
- **Hover**: scale `1.01×`, opacity +8%, blue border glow (`primary @ 25%`)
- **Press**: scale `0.98×`, opacity +15%, haptic feedback (`lightImpact`)
- **Refraction**: optional `ShaderMask` with radial gradient shimmer

#### Performance Modes (`GlassSettings`)
| Mode | Blur | Target |
|------|------|--------|
| `full` | 24σ | High-end devices |
| `medium` | 8σ | Mid-range devices |
| `none` | 0σ solid fills | Low-end devices |

### 8.4 Animations

| Animation | Curve | Duration | Usage |
|-----------|-------|----------|-------|
| Tab switch | `easeInOutQuad` | 300ms | Tab transitions |
| Menu pop-in | `easeOutExpo` | 400ms | Menus, fade-in stagger |
| Card press | `easeOutCubic` | 200ms | Tap/hover scale |
| `LiquidFadeIn` | `easeOutExpo` | 400ms | Staggered content load (20dp slide-up + fade) |
| Scroll physics | `BouncingScrollPhysics` | `fast` deceleration | All scrollable lists |

### 8.5 Responsive Scaling

| Breakpoint | Width | Layout |
|------------|-------|--------|
| Mobile | < 600dp | Single column, bottom nav |
| Tablet | 600–1023dp | Wider padding |
| Desktop | ≥ 1024dp | Sidebar + multi-column |
| Wide | ≥ 1400dp | Extra-wide panels |

#### `Responsive.sp()` — Proportional Scaling
- **Reference**: 375dp (iPhone SE)
- **Scale**: `(viewportWidth / 375).clamp(0.65, 1.6)`
- **Desktop mode (`dp()`)**: Uses 1440dp reference, clamped `0.7–1.3×`
- **Horizontal padding**: Desktop `24sp` · Tablet `16sp` · Mobile `10sp`
- **Card width**: `28%` of available width, clamped `160–300dp`

### 8.6 Theme Config (`AppTheme.darkTheme`)

| Component | Setting |
|-----------|---------|
| Material3 | `true` |
| AppBar | Transparent (`backgroundDark @ 80%`), no elevation |
| Cards | `glassDark` fill, 0 elevation, `14dp` radius, `white @ 5%` border |
| Input fields | `desktopSearchFill`, `10dp` radius, no border |
| SnackBar | Floating, `cardDark` fill, `10dp` radius |
| FAB | `primary` fill, `12dp` radius, 0 elevation |
| Dividers | `white10`, `0.5px` thickness |

---

## 9. 12-Step Problem-Solving Framework

> **MANDATORY** for all failure investigation and resolution. Follow in exact order.

| Step | Action | Rule |
|------|--------|------|
| **1. Define** | What is the problem? | Focus on understanding — no blame. |
| **2. Validate** | Is it really a problem? | Pause. Does this actually need solving, or is it just uncomfortable? |
| **3. Expand** | What else is the problem? | Look for hidden or related issues you might be missing. |
| **4. Trace** | How did the problem occur? | Reverse-engineer the timeline from the very beginning. |
| **5. Brainstorm** | What are ALL possible solutions? | No filtering yet — list everything. |
| **6. Evaluate** | What is the best solution right now? | Consider current resources, time, and constraints. |
| **7. Decide** | Commit to the best solution. | No second-guessing once decided. |
| **8. Assign** | Break into actionable steps. | Systematic, accountable, specific. |
| **9. Measure** | Define what "solved" looks like. | What does the completed solution look like? What are its expected effects? |
| **10. Start** | Take the first action. | Momentum matters. |
| **11. Complete** | Finish every step you planned. | No half-measures. |
| **12. Review** | Compare outcomes against step 9. | Not satisfied? Repeat steps 1–11 until it's solved. |

---

*Last updated: February 26, 2026*
*Authored by: LeoBook Engineering Team*

