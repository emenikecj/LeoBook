"""
Football.com Booking Package
Main entry point for Football.com betting operations.
"""

from .navigator import load_or_create_session, perform_login, extract_balance, navigate_to_schedule, select_target_date
from .extractor import extract_league_matches, validate_match_data
from .matcher import match_predictions_with_site, filter_pending_predictions
from .booker import book_single_match, place_multi_bet_from_codes, force_clear_slip, check_and_perform_withdrawal

from .football_com import run_football_com_booking

__all__ = [
    'run_football_com_booking',
    'load_or_create_session',
    'perform_login',
    'extract_balance',
    'navigate_to_schedule',
    'select_target_date',
    'extract_league_matches',
    'validate_match_data',
    'match_predictions_with_site',
    'filter_pending_predictions',
    'book_single_match',
    'place_multi_bet_from_codes',
    'force_clear_slip',
    'check_and_perform_withdrawal'
]
