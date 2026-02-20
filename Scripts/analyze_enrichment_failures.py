"""Analyze all EnrichmentFailure diagnostic folders to find patterns."""
import os, json

FAILURES_DIR = os.path.join("Data", "Logs", "EnrichmentFailures")

empty_html_count = 0
real_html_count = 0
blank_png_count = 0
real_png_count = 0
total = 0
sample_real = []

for folder in sorted(os.listdir(FAILURES_DIR)):
    folder_path = os.path.join(FAILURES_DIR, folder)
    if not os.path.isdir(folder_path):
        continue
    total += 1
    
    html_file = os.path.join(folder_path, "source.html")
    png_file = os.path.join(folder_path, "failure.png")
    
    html_content = ""
    if os.path.exists(html_file):
        with open(html_file, "r", encoding="utf-8") as f:
            html_content = f.read().strip()
    
    png_size = os.path.getsize(png_file) if os.path.exists(png_file) else 0
    
    is_empty_html = len(html_content) < 50 or html_content == "<html><head></head><body></body></html>"
    is_blank_png = png_size < 5000  # blank white PNGs are ~4KB
    
    if is_empty_html:
        empty_html_count += 1
    else:
        real_html_count += 1
        if len(sample_real) < 3:
            sample_real.append((folder, len(html_content), png_size))
    
    if is_blank_png:
        blank_png_count += 1
    else:
        real_png_count += 1

print(f"=== EnrichmentFailures Analysis ===")
print(f"Total diagnostic folders: {total}")
print(f"")
print(f"HTML Status:")
print(f"  Empty/blank HTML: {empty_html_count} ({100*empty_html_count/total:.0f}%)")
print(f"  Real HTML content: {real_html_count} ({100*real_html_count/total:.0f}%)")
print(f"")
print(f"Screenshot Status:")
print(f"  Blank/tiny PNG (<5KB): {blank_png_count} ({100*blank_png_count/total:.0f}%)")
print(f"  Real PNG (>5KB): {real_png_count} ({100*real_png_count/total:.0f}%)")
print(f"")

if sample_real:
    print(f"Folders with REAL content (worth examining):")
    for folder, html_len, png_sz in sample_real:
        print(f"  {folder}: HTML={html_len} chars, PNG={png_sz} bytes")
else:
    print("ALL folders have empty/blank content — this is a page-loading failure, not an AIGO logic failure.")
