# withdrawal_checker.py: withdrawal_checker.py: Logic for managing automated withdrawal proposals.
# Part of LeoBook Core — System
#
# Functions: calculate_proposed_amount(), get_latest_win(), check_triggers(), propose_withdrawal(), check_withdrawal_approval(), execute_withdrawal()

import asyncio
from datetime import datetime as dt, timedelta
from pathlib import Path
from Core.System.lifecycle import state, log_audit_state, log_state
from Data.Access.db_helpers import log_audit_event

# Local state for withdrawals
pending_withdrawal = {
    "active": False,
    "amount": 0.0,
    "proposed_at": None,
    "expiry": None,
    "approved": False
}

def calculate_proposed_amount(balance: float, latest_win: float) -> float:
    """v2.7 Calculation: Min(30% balance, 50% latest win)."""
    val = min(balance * 0.30, latest_win * 0.50)
    # Ensure floor of 5,000 remains in account
    if balance - val < 5000:
        val = balance - 5000
    
    return max(0.0, float(int(val))) # Round to whole number

def get_latest_win() -> float:
    """Retrieves the latest win amount from audit logs or state."""
    return state.get("last_win_amount", 5000.0)

async def check_triggers(page=None) -> bool:
    """v2.7 Triggers."""
    balance = state.get("current_balance", 0.0)
    if balance >= 10000 and get_latest_win() >= 5000:
        return True
    return False

async def propose_withdrawal(amount: float):
    global pending_withdrawal
    if pending_withdrawal["active"]:
        return

    pending_withdrawal.update({
        "active": True,
        "amount": amount,
        "proposed_at": dt.now(),
        "expiry": dt.now() + timedelta(hours=2),
        "approved": False
    })

    print(f"   [Withdrawal] Proposal active: ₦{amount:.2f} (Awaiting LeoBook Web/App approval)")
    # Persist proposal to Supabase via audit log for Web/App approval UI
    log_audit_event(
        "WITHDRAWAL_PROPOSAL",
        f"Proposed: ₦{amount:.2f} | Balance: ₦{state.get('current_balance', 0):.2f}",
        status="pending"
    )

async def check_withdrawal_approval() -> bool:
    """
    Check if a pending withdrawal has been approved via LeoBook Web/App.
    Reads approval status from Supabase audit_log (flagged by Web/App).
    """
    if not pending_withdrawal["active"]:
        return False

    # Check expiration
    if pending_withdrawal["expiry"] and dt.now() > pending_withdrawal["expiry"]:
        print("   [Withdrawal] Proposal expired (Time-to-Live exceeded). Resetting.")
        log_audit_event("WITHDRAWAL_EXPIRED", f"Expired proposal: ₦{pending_withdrawal['amount']}", status="reset")
        pending_withdrawal.update({"active": False, "amount": 0.0, "expiry": None})
        return False
    
    try:
        from Data.Access.sync_manager import get_supabase_client
        sb = get_supabase_client()
        if sb:
            result = sb.table("audit_log").select("status").eq(
                "event_type", "WITHDRAWAL_APPROVAL"
            ).order("created_at", desc=True).limit(1).execute()
            
            if result.data and result.data[0].get("status") == "approved":
                pending_withdrawal["approved"] = True
                print("   [Withdrawal] ✅ Approval received from LeoBook Web/App.")
                return True
    except Exception as e:
        print(f"   [Withdrawal] Approval check failed: {e}")
    
    return False

async def execute_withdrawal(amount: float):
    """Executes the withdrawal using an isolated browser context (v2.8)."""
    print(f"   [Execute] Starting approved withdrawal for ₦{amount:.2f}...")
    from playwright.async_api import async_playwright
    
    async with async_playwright() as p:
        user_data_dir = Path("Data/Auth/ChromeData_v3").absolute()
        try:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=str(user_data_dir),
                headless=True,
                viewport={'width': 375, 'height': 612}
            )
            page = await context.new_page()
            
            from Modules.FootballCom.booker.withdrawal import check_and_perform_withdrawal
            success = await check_and_perform_withdrawal(page, state["current_balance"], last_win_amount=amount*2)
            
            if success:
                log_state("Withdrawal", f"Executed ₦{amount:,.2f}", "Web/App Approval")
                log_audit_event("WITHDRAWAL_EXECUTED", f"Executed: ₦{amount}", state["current_balance"], state["current_balance"]-amount, amount)
                state["last_withdrawal_time"] = dt.now()
                # Reset pending state
                pending_withdrawal.update({"active": False, "amount": 0.0, "proposed_at": None, "expiry": None, "approved": False})
            else:
                print("   [Execute Error] Withdrawal process failed.")
                
            await context.close()
        except Exception as e:
            print(f"   [Execute Error] Failed to launch context for withdrawal: {e}")
