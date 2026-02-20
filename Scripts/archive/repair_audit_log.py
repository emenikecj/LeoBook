
import csv
import os
import uuid
from pathlib import Path

# Paths
DB_DIR = Path("Data/Store")
AUDIT_LOG_CSV = DB_DIR / "audit_log.csv"
BACKUP_CSV = DB_DIR / "audit_log_backup.csv"

# Target Header
TARGET_HEADER = ['id', 'timestamp', 'event_type', 'description', 'balance_before', 'balance_after', 'stake', 'status']

def is_valid_uuid(val):
    try:
        uuid.UUID(str(val))
        return True
    except:
        return False

def repair_audit_log():
    if not AUDIT_LOG_CSV.exists():
        print("No audit log found. Skipping.")
        return

    print(f"Repairing {AUDIT_LOG_CSV}...")
    
    # Backup
    import shutil
    shutil.copy(AUDIT_LOG_CSV, BACKUP_CSV)
    
    repaired_rows = []
    
    with open(AUDIT_LOG_CSV, 'r', newline='', encoding='utf-8') as f:
        # Detect if it has a header
        sample = f.read(1024)
        f.seek(0)
        has_header = csv.Sniffer().has_header(sample)
        reader = csv.reader(f)
        
        if has_header:
            actual_header = next(reader)
            print(f"Existing header found: {actual_header}")
        
        for row in reader:
            if not row: continue
            
            # Try to identify columns
            # Case 1: Row starts with UUID (id is first)
            if is_valid_uuid(row[0]):
                # Row is likely: [id, timestamp, event_type, description, bal_b, bal_a, stake, status, ...]
                cleaned_row = {
                    'id': row[0],
                    'timestamp': row[1] if len(row) > 1 else '',
                    'event_type': row[2] if len(row) > 2 else '',
                    'description': row[3] if len(row) > 3 else '',
                    'balance_before': row[4] if len(row) > 4 else '',
                    'balance_after': row[5] if len(row) > 5 else '',
                    'stake': row[6] if len(row) > 6 else '',
                    'status': row[7] if len(row) > 7 else ''
                }
            # Case 2: Row starts with Timestamp (id is later)
            elif len(row) > 0 and (row[0].startswith('202') or '.' in row[0] or '-' in row[0]):
                # Row is likely: [timestamp, event_type, description, bal_b, bal_a, stake, status, id, ...]
                # Search for UUID in the row
                found_id = str(uuid.uuid4())
                for i, val in enumerate(row):
                    if is_valid_uuid(val):
                        found_id = val
                        break
                
                cleaned_row = {
                    'id': found_id,
                    'timestamp': row[0],
                    'event_type': row[1] if len(row) > 1 else '',
                    'description': row[2] if len(row) > 2 else '',
                    'balance_before': row[3] if len(row) > 3 else '',
                    'balance_after': row[4] if len(row) > 4 else '',
                    'stake': row[5] if len(row) > 5 else '',
                    'status': row[6] if len(row) > 6 else ''
                }
            else:
                # Fallback: Just skip or assign new UUID
                continue
                
            repaired_rows.append(cleaned_row)

    # Write back with correct header
    with open(AUDIT_LOG_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=TARGET_HEADER, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(repaired_rows)
        
    print(f"Repaired {len(repaired_rows)} rows. Backup saved to {BACKUP_CSV}.")

if __name__ == "__main__":
    repair_audit_log()
