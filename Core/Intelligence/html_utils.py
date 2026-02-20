# html_utils.py: html_utils.py: Optimized HTML cleaning for AI analysis.
# Part of LeoBook Core — Intelligence (AI Engine)
#
# Functions: clean_html_content()

"""
HTML Utilities Module
Handles HTML content cleaning and processing for visual analysis.
"""

import re


def clean_html_content(html_content: str) -> str:
    """Clean HTML content to reduce token usage while preserving structure"""
    import re

    # 1. Remove script, style, and svg tags (heavy and non-functional for selectors)
    html_content = re.sub(r"<script.*?</script>", "", html_content, flags=re.DOTALL | re.IGNORECASE)
    html_content = re.sub(r"<style.*?</style>", "", html_content, flags=re.DOTALL | re.IGNORECASE)
    html_content = re.sub(r"<svg.*?</svg>", "[SVG]", html_content, flags=re.DOTALL | re.IGNORECASE)

    # 2. Remove common non-essential attributes to save tokens
    # Removing 'style', 'path', 'd', 'viewBox' etc.
    html_content = re.sub(r'\sstyle="[^"]*"', '', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'\son[a-z]+="[^"]*"', '', html_content, flags=re.IGNORECASE)

    # 3. Collapse whitespace
    html_content = re.sub(r'\s+', ' ', html_content)

    # 4. Truncate - Increased limit to 15,000 for better context
    # Grok has a large context window, 5000 was too aggressive
    return html_content[:15000]
