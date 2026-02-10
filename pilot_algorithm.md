# Pilot X - LeoBook Core Algorithms

## Modular UI Architecture (Stitch System)
Pilot X utilizes the **Stitch Design System** (versions v1 to v10) to ensure a high-fidelity, data-driven user experience. 

- **Stitch v1 (Root & Layout)**: Standardizes the `FootnoteSection`, `HomeScreen` headers, and the global date-strip pill system.
- **Stitch v2 (Search Flow)**: Categorized results logic (Leagues vs Matches) with frequency-based "Popular Teams" rankings.
- **Stitch v4 (UI Atoms)**: Explicit brand tokenization (Electric Blue #137FEC) and Lexend-based typography hierarchy.
- **Stitch v6 (Recommendations)**: Vertical accent line indicators and live-pulse tagging for high-confidence predictions.

This document serves as the **Source of Truth** for Pilot X (LeoBook), a semi-autonomous game assistant.

---

## 🏗️ System Architecture

The system is split into two main components:
1. **Core Processing (Python)**: Handles data extraction, AI analysis, and prediction generation.
2. **Mobile App (Flutter)**: Provides a premium UI for viewing matches, predictions, and news.

### Core Processing Flow
1. **Phase 1: Analysis & Prediction**:
    - [manager.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Modules/Flashscore/manager.py): Orchestrates match schedule harvesting.
    - [rule_engine.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/Intelligence/rule_engine.py): Executes AI models and heuristic rules to generate predictions.
    - [recommend_bets.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Scripts/recommend_bets.py): Aggregates predictions into high-confidence recommendations and exports `recommended.json`.

### Flutter App Architecture (Clean Architecture / MVVM)
- **Data Layer**:
    - `DataRepository`: **Platform-aware** - uses SQLite database (7.77 MB) for mobile/desktop, CSV for web.
    - `PredictionsDatabase`: Helper class managing database download, caching, and SQL queries with indexes on fixture_id, date, and league (mobile/desktop only).
    - **Performance**: SQLite on native platforms eliminates CSV parsing overhead. Web uses CSV with extended timeout (180s) and SharedPreferences caching.
    - **Offline Support**: Database persists locally in app documents directory (mobile/desktop). Web uses SharedPreferences cache.
    - **Caching**: Implements `shared_preferences` based cache-aside pattern for all platforms.
    - `NewsRepository`: Fetches latest sports news from configured sources.

- **Logic Layer**:
    - `HomeCubit`: Manages the state of the dashboard, coordinating data from multiple repositories.
- **Presentation Layer**:
    - `HomeScreen`: Dashboard with featured matches, top predictions carousel, and "All Predictions" feed.
    - `AllPredictionsScreen`: Dedicated full-page view for the "All Predictions" list with date-specific search/filter controls.
    - `TopPredictionsScreen`: Detailed list of highly recommended bets with confidence scores.
    - `MatchDetailsScreen`: Comprehensive match view with scores and detailed predictions.
    - `FilterModal`: Premium bottom-sheet for multi-category filtering (Leagues, Odds, Types).

---

## 🔄 Data Merging & Navigation Logic

### All Predictions & Content Flow
1. **Source**: Fetches from `raw.githubusercontent.com`.
2. **Global Filtering (Date & Sport)**:
    - Every section (Featured Carousel, Top Recommendations, and All Predictions) is synchronized to the `selectedDate` and `selectedSport` in `HomeCubit`.
    - When the user selects a date (e.g., Feb 11) or a sport (e.g., Basketball), the app filters the entire data state to only show content matching *both* criteria.
    - **Sport Logic**: Extracted from `match_link` (URLs) for matches and `league` names for recommendations.
    - **Standard Filter Suite**: Includes a dedicated `FilterModal` linked to `HomeCubit`. This allows real-time refining of predictions by league, odds range (1.0 - 5.0+), and specific outcomes (Home Win, BTTS, etc.).
3. **UI Sync**: The `HeaderSection` and `FilterModal` act as the master controllers for these filters, providing a unified and responsive dashboard experience.

### Top Predictions Flow
1. **Source**: `recommend_bets.py` filters `predictions.csv` using reliability stats and confidence scores.
2. **Bridge**: The script exports `recommended.json` which includes a `fixture_id`.
3. **App Logic**:
    - `HomeCubit` fetches `recommended.json`.
    - `TopPredictionsScreen` displays these recommendations using `RecommendationCard`.
    - **Linking**: When a recommendation is tapped, the app uses the `fixture_id` to find the corresponding `MatchModel` from the full schedule and navigates to `MatchDetailsScreen`.

### Match Card Logic
- Every match card (Standard or Recommendation) is wrapped in a `GestureDetector`.
- On tap, the app pushes `MatchDetailsScreen` to the navigation stack, providing immediate access to in-depth analysis.

---

## 🎨 Standardized UI Component Library
The LeoBook Flutter app adheres to a strict design system (Stitch Standard) to ensure a premium, data-rich experience:

1. **Header (TopBar + Nav)**: Sticky architecture with date-strip synchronization and interactive search/filter controls.
2. **Featured Match Card**: High-impact 16:10 cards using stadium imagery, gradient overlays, and glassmorphism for prediction details.
3. **Standard Match Card**: Clean typography with larger team logos, "VS" italics, and a dedicated prediction/odds row.
4. **Live Match Card**: Features a red "LIVE" pulse badge and real-time score layout.
5. **Responsible Gaming Footnote**: Mandatory ethical safeguards and legal disclaimers.

---

## 🛠️ Code Quality & Modernization
To maintain a production-grade codebase, Pilot X follows strict modernization standards:

1.  **Rendering Engine (Flutter 3.27+)**: Migrated all deprecated `Color.withOpacity` calls to the new `Color.withValues(alpha: ...)` API to ensure compatibility with future Impeller rendering optimizations.
2.  **Standardized Logging**: Replaced all raw `print` statements in data layers with `debugPrint` (from `foundation.dart`) to prevent log flooding in production and improve performance.
3.  **Modern Reference Checks**: Fixed stale IDE references in test suites (e.g., `widget_test.dart`) to ensure 100% pass rate in CI/CD pipelines.

---

## 🔒 Safety & Standards
- **Standardized Selectors**: All UI selectors are stored in `knowledge.json`.
- **Fractional Kelly Staking**: Used for bankroll management in autonomous phases.
- **MVVM Pattern**: Ensures a decoupled, testable, and maintainable frontend.
