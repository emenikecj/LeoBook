# LeoBook: State Comparison & Upgrade Gap Analysis

This document details the difference between the current implementation of LeoBook and the required "Observe, Decide, Act" algorithm upgrade.

| Feature Area | Current State | Required Upgrade | Gap / Action |
| :--- | :--- | :--- | :--- |
| **Startup / Init** | `Leo.py` initializes CSVs and attempts to start AI server unconditionally in `main` loop (though `start_ai_server` handles checks). | **Smart AI Server**: Check port 8000 first. Only start if needed. Explicit state tracking (`state.ai_server_ready`). | Minor. Need to refine `Leo.py` to be more state-aware and explicit about *why* the server is starting (only for Phase 2 matching). |
| **Phase 0: Review** | Basic placeholder or legacy `outcome_reviewer.py`. | **Structured Review**: Load booked matches -> Update status in `predictions.csv` & `football_com_matches.csv` -> Print Accuracy. | **High**. Needs strictly defined `run_review_process` that updates *both* CSVs to close the feedback loop. |
| **Phase 1: Analysis (Flashscore)** | Navigates to Home -> Clicks "Scheduled" -> Extracts matches likely for "Today" or iterated days. | **Target Date Focus**: Switch to Scheduled Tab -> Extract specifically for *Target Date*. Batch process matches for that date. | Moderate. The logic needs to be stricter about "Target Date" extraction to ensure we aren't mixing days or missing future scheduled games. |
| **Phase 2: Booking (Structure)** | **Live Accumulator Build**: Matches predictions -> Visits match URL -> Adds to slip -> Finalizes when full. | **Two-Stage Process**: <br>1. **Phase 2a (Harvest)**: Visit match -> Book *Single* -> **Extract Code** -> Clear Slip. <br>2. **Phase 2b (place)**: Load Codes -> Build Multi from Codes -> Place. | **CRITICAL**. This is the biggest architectural change. Current code builds the slip "live". New requirements demand "Booking Codes" first for reliability and reusability. |
| **Phase 2: Validation** | Checks balance, logged-in state. | **Strict Sequence**: Login Check -> Balance Check -> **Clear Slip** (Verify count=0). | Moderate. Ensure "Clear Slip" is aggressive and verified before *every* single bet booking step in Phase 2a. |
| **Phase 2: URL Resolution** | specific `matcher.py` logic. | **LLM Fallback**: If cache miss -> Search -> Extract -> LLM Match (using `football_com_matches.csv` cache). | Moderate. Ensure the LLM matching flow is robust and only runs if the AI server is actually ready (as per Startup). |
| **Manual Withdrawal** | Basic file exists (`withdrawal.py`). | **Full Sequence**: Amount -> Submit -> **Extract Info** -> Confirm -> PIN -> Verify "Pending" -> Update `withdrawals.csv`. | **High**. The `withdrawal.py` needs to be fully implemented/verified against the specific steps (Done in recent fix). |

## Key Architectural Shift: The "Harvest" Strategy

The most significant change is in **Phase 2**. 

**Current Flow:**
`Prediction` -> `Match URL` -> `Add to Slip` -> `Add next...` -> `Place Bet`

**New Flow:**
1. **Harvest:** `Prediction` -> `Match URL` -> `Book Single` -> **`Save Code`** -> `Clear Slip`
2. **Execute:** `Load Codes` -> `Load URL (via Code)` -> `Add to Slip` -> `Place Multi Bet`

### Why this change?
1.  **Safety**: If a multi-bet build fails halfway (e.g., browser crash), we lose progress. With codes, we have saved the "hard work" of finding outcomes.
2.  **Speed**: Loading a booked bet code is faster/more reliable than searching for markets/outcomes repeatedly.
3.  **Flexibility**: Allows constructing different multi-bets (e.g., different groupings) from the same pool of valid single codes.

## Implementation Priorities
1.  **Fix Import Error**: (Completed - `withdrawal_py` fix).
2.  **Phase 2a (Single Booking)**: Implement `book_single_match` to extract codes.
3.  **Phase 2b (Multi Placement)**: Implement logic to build slip from codes.
4.  **Orchestrator**: Update `Leo.py` to drive these two distinct phases.
