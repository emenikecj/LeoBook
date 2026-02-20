import re

data = open('leo_session_20260220_070630.log', encoding='utf-8', errors='replace').read()
lines = data.split('\n')
print(f'Total lines: {len(lines)}')

# CRITICAL ERROR match names
crits = re.findall(r"CRITICAL ERROR.*?process_match_task_(.+?)[\'\"\.]", data)
print(f'\n=== CRITICAL ERROR matches ({len(set(crits))} unique) ===')
for m in sorted(set(crits)):
    print(f'  - {m}')

# File Error details
ferrs = [l.strip() for l in lines if 'File Error' in l]
print(f'\n=== File Errors ({len(ferrs)}) ===')
for e in sorted(set(ferrs)):
    print(f'  {e}')

# Fallback Error  
fberrs = [l.strip() for l in lines if 'Fallback Error' in l]
print(f'\n=== Fallback Errors ({len(fberrs)}) ===')
for e in sorted(set(fberrs)):
    print(f'  {e}')

# TIMEOUT leagues
timeouts = [l.strip() for l in lines if 'TIMEOUT' in l]
print(f'\n=== League Extractor TIMEOUTs ({len(timeouts)}) ===')
for t in sorted(set(timeouts)):
    print(f'  {t}')

# Prediction accuracy 0%
acc = [l.strip() for l in lines if '0.0% Accurate' in l]
print(f'\n=== 0% Accuracy ({len(acc)}) ===')
for a in acc:
    print(f'  {a}')

# Parity fails
parity = [l.strip() for l in lines if 'Parity Fail' in l or 'PARITY ERROR' in l]
print(f'\n=== Parity Failures ({len(parity)}) ===')
for p in parity:
    print(f'  {p}')

# Selector failures
selfs = [l.strip() for l in lines if 'Selector Failure' in l]
print(f'\n=== Selector Failures ({len(selfs)}) ===')
for s in sorted(set(selfs)):
    print(f'  {s}')

# Schema / over_2.5 errors
schema = [l.strip() for l in lines if 'over_2.5' in l]
print(f'\n=== Schema Errors (over_2.5 column) ({len(schema)}) ===')
for s in sorted(set(schema)):
    print(f'  {s}')

# Page/Target crash summary
streamer_errs = [l.strip() for l in lines if 'Extraction error' in l and 'Streamer' in l]
print(f'\n=== Streamer Extraction Errors ({len(streamer_errs)}) ===')
reasons = {}
for s in streamer_errs:
    if 'Target crashed' in s:
        reasons['Target crashed'] = reasons.get('Target crashed', 0) + 1
    elif 'Page crashed' in s:
        reasons['Page crashed'] = reasons.get('Page crashed', 0) + 1
    elif 'NoneType' in s:
        reasons["'NoneType' object"] = reasons.get("'NoneType' object", 0) + 1
    else:
        reasons['Other'] = reasons.get('Other', 0) + 1
for k,v in reasons.items():
    print(f'  {v}x {k}')

# Page.goto crashed
goto_crash = [l.strip() for l in lines if 'Page.goto: Page crashed' in l]
print(f'\n=== Page.goto crashes ({len(goto_crash)}) ===')
for g in goto_crash:
    print(f'  {g}')

# Navigation failed
nav_fail = [l.strip() for l in lines if 'Navigation failed' in l]
print(f'\n=== Navigation failures ({len(nav_fail)}) ===')
for n in nav_fail:
    print(f'  {n}')

# DB UPSERT Warning count
dbw = len([l for l in lines if 'DB UPSERT Warning' in l])
print(f'\n=== DB UPSERT Warnings: {dbw} ===')
print('  All: Skipping entry due to missing unique key fixture_id')

# Import errors
imp = [l.strip() for l in lines if 'cannot import name' in l]
print(f'\n=== Import Errors ({len(imp)}) ===')
for i in sorted(set(imp)):
    print(f'  {i}')
