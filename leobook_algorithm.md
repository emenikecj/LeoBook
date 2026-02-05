# LeoBook v2.7 Algorithm & Codebase Reference

This document serves as the **Source of Truth** for the LeoBook Autonomous Betting System. It provides a granular, step-by-step breakdown of the execution flow, mapped to specific files and functions.

---

## 🏗️ System Architecture

The system operates in a continuous `while True` loop inside [Leo.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Leo.py), executing four distinct phases sequentially every 6 hours.

For a high-level visual representation, see: [leobook_algorithm.mmd](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/leobook_algorithm.mmd)

### **Phase 0: Initialization & Outcome Review**
**Objective**: Observe past performance, update financial records, and adjust AI learning weights.

1.  **System Initialization**:
    - [Leo.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Leo.py): `main()` calls `init_csvs()`.
    - [db_helpers.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Data/Access/db_helpers.py): `init_csvs()` ensures all storage files and headers exist.
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
**Objective**: Mirror predictions on Football.com, generate booking codes, and place bets.

1.  **Session & Preparation**:
    - [fb_manager.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Modules/FootballCom/fb_manager.py): `run_football_com_booking()` orchestrates the acting phase.
    - [fb_session.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Modules/FootballCom/fb_session.py): `launch_browser_with_retry()` initializes the anti-detect session.
    - [navigator.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Modules/FootballCom/navigator.py): `load_or_create_session()` and `extract_balance()` validate the account state.

2.  **Phase 2a: Harvest (Code Generation)**:
    - [fb_url_resolver.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Modules/FootballCom/fb_url_resolver.py): `resolve_urls()` searches for match pages.
    - [matcher.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Modules/FootballCom/matcher.py): `match_predictions_with_site()` uses fuzzy matching and [llm_matcher.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/Intelligence/llm_matcher.py) (threshold 0.60) to resolve fixtures.
    - [booking_code.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Modules/FootballCom/booker/booking_code.py): `harvest_single_match_code()` worker:
        - Navigates to match URL.
        - [mapping.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Modules/FootballCom/booker/mapping.py): `find_market_and_outcome()` locates UI elements.
        - [ui.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Modules/FootballCom/booker/ui.py): `robust_click()` handles selections.
        - Checks odds (Min 1.20).
        - Extracts 6-8 digit booking code and saves to `site_matches.csv`.
    - [slip.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Modules/FootballCom/booker/slip.py): `force_clear_slip()` ensures the slip is empty after each code harvest.

3.  **Phase 2b: Execution (Placement)**:
    - [placement.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Modules/FootballCom/booker/placement.py): `place_multi_bet_from_codes()`:
        - Re-injects harvested codes into the betslip.
        - Calculates stake via `calculate_kelly_stake()` (Fractional Kelly c=0.25).
        - Executes final placement and logs event via `log_audit_event()`.

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
