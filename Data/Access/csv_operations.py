# csv_operations.py: csv_operations.py: Low-level CSV read/write and UPSERT logic.
# Part of LeoBook Data — Access Layer
#
# Functions: _read_csv(), _append_to_csv(), _write_csv(), upsert_entry()

"""
CSV Operations Module
Low-level CSV file manipulation utilities and database operations.
Responsible for reading, writing, appending, and upserting CSV data safely.
"""

import os
import csv
from typing import Dict, Any, List

# --- CSV File Paths ---
DB_DIR = "Data/Store"

def _read_csv(filepath: str) -> List[Dict[str, str]]:
    """Safely reads a CSV file into a list of dictionaries."""
    if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
        return []
    try:
        with open(filepath, 'r', newline='', encoding='utf-8') as f:
            return list(csv.DictReader(f))
    except Exception as e:
        print(f"    [File Error] Could not read {filepath}: {e}")
        return []

def _append_to_csv(filepath: str, data_row: Dict, fieldnames: List[str]):
    """Safely appends a single dictionary row to a CSV file."""
    file_exists = os.path.exists(filepath) and os.path.getsize(filepath) > 0
    try:
        with open(filepath, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            if not file_exists:
                writer.writeheader()
            writer.writerow(data_row)
    except Exception as e:
        print(f"    [File Error] Failed to write to {filepath}: {e}")

def _write_csv(filepath: str, data: List[Dict], fieldnames: List[str]):
    """Safely writes a list of dictionaries to a CSV file, overwriting it."""
    # This function is kept for operations that require a full rewrite, like updating statuses.
    try:
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(data)
    except Exception as e:
        print(f"    [File Error] Failed to write to {filepath}: {e}")

def upsert_entry(filepath: str, data_row: Dict, fieldnames: List[str], unique_key: str):
    """
    Performs a robust UPSERT (Update or Insert) operation on a CSV file.
    It reads the file, updates the row if it exists, or appends it if it's new.
    """
    unique_id = data_row.get(unique_key)
    if not unique_id:
        print(f"    [DB UPSERT Warning] Skipping entry due to missing unique key '{unique_key}'.")
        return

    all_rows = _read_csv(filepath)

    updated = False
    for row in all_rows:
        if row.get(unique_key) == unique_id:
            row.update(data_row)
            updated = True
            break

    if not updated:
        all_rows.append(data_row)

    _write_csv(filepath, all_rows, fieldnames)
