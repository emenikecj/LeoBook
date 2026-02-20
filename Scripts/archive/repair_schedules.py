import csv
import sys
import os

DB_DIR = r"c:\Users\Admin\Desktop\ProProjection\LeoBook\Data\Store"
SCHEDULES_CSV = os.path.join(DB_DIR, "schedules.csv")
BACKUP_CSV = os.path.join(DB_DIR, "schedules_backup.csv")

csv.field_size_limit(sys.maxsize)

def clean_schedules():
    if not os.path.exists(SCHEDULES_CSV):
        print("schedules.csv not found")
        return
    
    print("Repairing schedules.csv...")
    import shutil
    shutil.copy2(SCHEDULES_CSV, BACKUP_CSV)
    
    valid_rows = []
    skipped = 0
    with open(BACKUP_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            # Check if any field is absurdly large (e.g. > 50KB HTML blob leaked in)
            is_valid = True
            for k, v in row.items():
                if v and len(str(v)) > 50000:  
                    is_valid = False
                    break
            
            if is_valid:
                valid_rows.append(row)
            else:
                skipped += 1
                
    print(f"Read {len(valid_rows) + skipped} total rows. Skipped {skipped} oversized corrupted rows.")
    
    with open(SCHEDULES_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(valid_rows)
        
    print("Done rewriting schedules.csv")

if __name__ == "__main__":
    clean_schedules()
