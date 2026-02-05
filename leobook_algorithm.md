# LeoBook v2.7 Algorithm & Codebase Reference

This document serves as the **Source of Truth** for the LeoBook Autonomous Betting System. It provides a granular, step-by-step breakdown of the execution flow, mapped to specific files and functions.

---

## 🏗️ System Architecture

The system operates in a continuous `while True` loop inside [Leo.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Leo.py), executing four distinct phases sequentially every 6 hours.

For a high-level visual representation, see: [leobook_algorithm.mmd](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/leobook_algorithm.mmd)

### Phase 0: Initialization & Outcome Review
**Objective**: Observe past performance, update financial records, and adjust AI learning weights.

1.  **Singleton Protection**: [Leo.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Leo.py) uses a `leo.lock` file to prevent multiple instances from running simultaneously. This protects the Telegram Bot communication from `getUpdates` conflicts and ensures data integrity.
2.  **System Initialization**:
    - [Leo.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Leo.py): `main()` calls `init_csvs()`.
    - [db_helpers.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Data/Access/db_helpers.py): `init_csvs()` ensures all storage files and headers exist.
    - [Leo.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Leo.py): Starts the non-blocking Telegram listener task via [telegram_bridge.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/System/telegram_bridge.py).
    - [lifecycle.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/System/lifecycle.py): `setup_terminal_logging()` initializes process logs.
    - [telegram_bridge.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/System/telegram_bridge.py): `start_telegram_listener()` launches the interactive bot.

2.  **Outcome Processing**:
    - [review_outcomes.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Data/Access/review_outcomes.py): `run_review_process()` orchestrates the phase.
    - [outcome_reviewer.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Data/Access/outcome_reviewer.py):
        - `get_predictions_to_review()`: Filters `predictions.csv` for past matches needing review.
        - `process_review_task()`: Worker function (concurrency 5) that navigating to Flashscore via Playwright.
        - `get_final_score()`: Extracts the score from the match page or local `schedules.csv`.
        - `save_single_outcome()`: Updates `predictions.csv` with `actual_score` and `status: reviewed`.
    - [prediction_evaluator.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Data/Access/prediction_evaluator.py): `evaluate_prediction()` resolves the bet outcome (WIN/LOSS).
    - [prediction_accuracy.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Data/Access/prediction_accuracy.py): `print_accuracy_report()` generates the financial and model performance report.
    - [model.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/Intelligence/model.py): `update_learning_weights()` triggers the [LearningEngine](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/Intelligence/learning_engine.py) to rotate weights.

---

### **Phase 1: Analysis & Prediction**
**Objective**: Analyze upcoming fixtures and generate betting selections using an ensemble of rules and AI.

1.  **Schedule Harvesting**:
    - [manager.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Modules/Flashscore/manager.py): `run_flashscore_analysis()` navigates to the Flashscore football page.
    - [fs_schedule.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Modules/Flashscore/fs_schedule.py): `extract_matches_from_page()` scrapes fixture metadata (IDs, URLs, Teams).

2.  **Modular Extraction**:
    - [fs_processor.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Modules/Flashscore/fs_processor.py): `process_match_task()` concurrent worker (concurrency 5).
    - [navigator.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Modules/Flashscore/navigator.py): `navigate_to_match()` and `activate_h2h_tab()`/`activate_standings_tab()` handles UI switching.
    - [extractor.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Modules/Flashscore/extractor.py): Calls specialized extractors:
        - [h2h_extractor.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/Browser/Extractors/h2h_extractor.py): `extract_h2h_data()` parses match history.
        - [standings_extractor.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/Browser/Extractors/standings_extractor.py): `extract_standings_data()` parses league tables.

3.  **Intelligence Analysis**:
    - [rule_engine.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/Intelligence/rule_engine.py): `RuleEngine.analyze()` coordinates sub-processes:
        - [ml_model.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/Intelligence/ml_model.py): `MLModel.predict()` evaluates patterns via trained models.
        - [goal_predictor.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/Intelligence/goal_predictor.py): `predict_goals_distribution()` calculates Poisson probabilities.
        - [tag_generator.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/Intelligence/tag_generator.py): Generates labels like `FORM_S2+` (Score 2+ often).
    - [betting_markets.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/Intelligence/betting_markets.py): `select_best_market()` chooses the safest market (conservative bias).
    - [db_helpers.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Data/Access/db_helpers.py): `save_prediction()` persists the final choice to `predictions.csv`.

---

### **Phase 2: Booking (Act)**
**Objective**: Harvest booking codes for single matches and then execute them as a multi-bet accumulator.

1.  **Session & Preparation**:
    - [fb_manager.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Modules/FootballCom/fb_manager.py): `run_football_com_booking()` orchestrates the acting phase.
    - [fb_session.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Modules/FootballCom/fb_session.py): `launch_browser_with_retry()` initializes the anti-detect session.
    - [navigator.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Modules/FootballCom/navigator.py): `load_or_create_session()` and `extract_balance()` validate the account state.
    - **Navigation Robustness**: Implements a mandatory **Scroll-Before-Click** strategy and pre-emptive popup dismissal before critical page transitions.

2. ### **Phase 2a: Harvest (Code Discovery)**
**Objective**: Connect prediction data to bookmaker URLs and extract individual booking codes.

- **Orchestrator**: [fb_url_resolver.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Modules/FootballCom/fb_url_resolver.py)
- **Logic**:
  - **Registry Check**: Checks `fb_matches.csv` for the target date before crawling.
  - **Match Matching (Direct)**: Re-uses URLs for already-mapped `fixture_id`s in the registry.
  - **Match Matching (AI Batch)**: Runs **AI Batch Prompt** against cached matches if registry is populated.
  - **Retry Logic**: Predictions with `status: failed_harvest` are automatically picked up for retry.
  - **Action**: Extracts sharing booking codes via [booking_code.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Modules/FootballCom/booker/booking_code.py).
    - [booking_code.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Modules/FootballCom/booker/booking_code.py): `place_bets_for_matches()` (renamed/repurposed to `harvest_booking_codes()`):
        - **Navigation**: Visits match URL, scrolls to outcome.
        - **Extraction**: Clicks outcome -> Opens slip -> Extracts code -> Saves to `fb_matches.csv`.
        - **Clearing**: Calls `force_clear_slip()` after *each* extraction to keep the UI clean.

3. ### **Phase 2b: Execution (Multi-Bet Placement)**
**Objective**: Inject all harvested codes and place a single combined accumulator bet.
- **Action**: [placement.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Modules/FootballCom/booker/placement.py): `place_multi_bet_from_codes()`:
    - **Injection**: Loops through harvested codes for the date and injects them via the bookmaker's "m-m" URL.
    - **Verification**: Confirms slip count matches.
    - **Staking**: Calculates **Fractional Kelly Stake** based on total balance.
    - **Placement**: Place & Confirm.
    - **Logging**: Updates `predictions.csv` to `status: booked`.

---

### **Phase 3: Completion & Withdrawal**
**Objective**: Monitor bankroll and execute payouts based on profit rules.

1.  **Bankroll Monitoring**:
    - [Leo.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Leo.py): Extracts post-booking balance.
    - [withdrawal_checker.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/System/withdrawal_checker.py): `check_triggers()` evaluates if a payout is due.

2.  **Payout Execution**:
    - [withdrawal.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Modules/FootballCom/booker/withdrawal.py): `check_and_perform_withdrawal()`:
        - Enforces 48h cooldown.
        - Calculates amount (30% Balance / 50% Last Win caps).
        - Enforces ₦5,000 baseline floor.
        - Executes `_execute_withdrawal_flow()` (PIN entry, confirmation, verification).
        - Logs success to `withdrawals.csv`.

---

## 🔒 Self-Healing & Resilience Layer

This layer operates globally across all phases to ensure the system never stops due to UI changes.

| Component | Responsibility | Key Hook |
| :--- | :--- | :--- |
| **Selector Manager** | Advanced retrieval. | [selector_manager.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/Intelligence/selector_manager.py): `get_selector_auto()` |
| **Visual Analyzer** | Screenshot processing. | [visual_analyzer.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/Intelligence/visual_analyzer.py): `analyze_page_and_update_selectors()` |
| **Healing AI** | Prompt engineering. | [prompts.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/Intelligence/prompts.py): `get_recovery_system_prompt()` |
| **Popup Handler** | Overlay removal. | [popup_handler.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/Intelligence/popup_handler.py): `fb_universal_popup_dismissal()` |
| **Recovery** | Stuck state escape. | [recovery.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/Intelligence/recovery.py): `attempt_visual_recovery()` |

---

**Manufacturer**: Emenike Chinenye James  
**Source of Truth**: Refactored Clean Architecture (v2.7)
