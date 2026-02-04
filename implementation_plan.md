# Implementation Plan - LeoBook Algorithm Upgrade (Refined)

## Goal Description
Upgrade LeoBook to strictly follow the "Observe, Decide, Act" algorithm with a **Harvest → Execute** strategy for Phase 2. This involves reliably extracting single bet codes (Harvest) before attempting to build multi-bets (Execute).

> [!IMPORTANT]
> **Constraint**: DO NOT make any changes to Phase 0 (Review) or Phase 1 (Flashscore Analysis). Focus strictly on Phase 2 (Booking), State Management, and Helpers.

## Key Architecture Shift: The "Harvest" Strategy
1.  **Phase 2a (Harvest)**: Visit Match -> Force Clear Slip -> Book Single -> **Extract Code** -> Save to CSV -> Force Clear Slip.
2.  **Phase 2b (Execute)**: Load Codes -> Build Multi -> Enforce Stake Rules -> Place.

## Proposed Changes

### 1. Helpers & DB (Foundation)
#### [MODIFY] [db_helpers.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Helpers/DB_Helpers/db_helpers.py)
- Update `init_csvs` to ensure `football_com_matches.csv` has these columns:
    - `fixture_id`, `football_com_url`, `booking_code`, `booking_url`, `status` (pending/booked/failed), `last_updated`, `home_team`, `away_team`, `date`, `league`.

### 2. State & Orchestration
#### [MODIFY] [Leo.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Leo.py)
- Implement global `state` dictionary (cycle counts, current phase, balances, error logs).
- Add `print_state()` helper for consistent logging.
- **Move AI Server Check**: Remove explicit check at startup. Move strictly to "on-demand" usage in Phase 2 URL resolution.

### 3. Phase 2: Booking (Refactored)

#### [NEW] [booking_code.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Sites/football_com/booker/booking_code.py)
- `book_single_match(page, match_url, prediction)`:
    - **Step 1**: `force_clear_slip(page)` (Fail hard if dirty).
    - **Step 2**: Navigate & Select Outcome (Min odds ≥ 1.20 check).
    - **Step 3**: Click "Book Bet".
    - **Step 4**: Extract `booking_code` and `booking_url`.
    - **Step 5**: Save to `football_com_matches.csv`.
    - **Step 6**: Dismiss modal & `force_clear_slip(page)`.

#### [MODIFY] [slip.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Sites/football_com/booker/slip.py)
- Implement `force_clear_slip(page)`:
    - Attempt to clear 3 times.
    - **Critical Failure**: If still dirty, delete `storage_state.json` and raise FatalSessionError to trigger browser restart.

#### [MODIFY] [football_com.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Sites/football_com/football_com.py)
- Refactor `run_football_com_booking`:
    - **Step 0**: Login & Balance Check.
    - **Step 1 (URL)**: Resolve URLs (use LLM only if cache miss).
    - **Step 2 (Harvest)**: Loop matches -> `book_single_match`.
    - **Step 3 (Execute)**: Use `place_multi_bet_from_codes`.

#### [MODIFY] [placement.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Sites/football_com/booker/placement.py)
- Implement `place_multi_bet_from_codes(page, codes)`:
    - Filter valid codes.
    - Add to slip (up to 12).
    - **Stake Rules**: `min(1% bal, N1)` to `max(50% bal)`.
    - Place & Confirm.

### 4. Manual Withdrawal
#### [MODIFY] [withdrawal.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Sites/football_com/booker/withdrawal.py)
- Add verification logic before filling amount:
    - Max Limit: `min(30% balance, 50% latest_win)`.
    - Min Limit: `N500`.

## Verification Plan
1.  **Slip Clearing**: Test `force_clear_slip` with a pre-filled slip.
2.  **Single Harvest**: Run `book_single_match` on 1 match, verify code in CSV.
3.  **Multi Place**: Run `place_multi_bet_from_codes` with 2 dummy codes (low stake).
4.  **Full Cycle**: Dry run `Leo.py` to check state logging and phase transitions.
