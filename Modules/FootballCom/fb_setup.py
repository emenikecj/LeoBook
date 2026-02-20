# fb_setup.py: fb_setup.py: Pre-booking initialization tasks.
# Part of LeoBook Modules — Football.com
#
# Functions: get_pending_predictions_by_date()

from datetime import datetime as dt
from .matcher import filter_pending_predictions

async def get_pending_predictions_by_date():
    """
    Retrieves pending predictions and groups them by date.
    Returns: Dict[date_str, list[predictions]] or None
    """
    pending_predictions = await filter_pending_predictions()
    if not pending_predictions:
        print("  [Info] No pending predictions to book.")
        return None

    predictions_by_date = {}
    today = dt.now().date()
    for pred in pending_predictions:
        d_str = pred.get('date')
        if d_str:
            try:
                if dt.strptime(d_str, "%d.%m.%Y").date() >= today:
                    predictions_by_date.setdefault(d_str, []).append(pred)
            except: continue
            
    if not predictions_by_date:
        print("  [Info] No future predictions found.")
        return None
    
    return predictions_by_date
