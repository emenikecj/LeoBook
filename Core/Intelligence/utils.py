# utils.py: utils.py: AI-related utility functions.
# Part of LeoBook Core — Intelligence (AI Engine)
#
# Functions: clean_json_response()

"""
Intelligence Utils Module
Utility functions for the Core.Intelligence package.
"""

import re


def clean_json_response(text: str) -> str:
    """
    Cleans Leo AI response to ensure valid JSON parsing.
    Removes Markdown fences and attempts to fix common escape issues.
    """
    if not text:
        return "{}"

    # 1. Remove Markdown code blocks
    text = re.sub(r"^```json\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^```\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"```$", "", text, flags=re.MULTILINE)

    # 2. Fix simple invalid escapes (e.g., \d in strings -> \\d)
    # This matches a backslash NOT followed by a valid escape char (", \, /, b, f, n, r, t, u)
    # and doubles it. This prevents "Invalid \escape" errors.
    text = re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", text)

    return text.strip()


def clean_html_content(html_content: str) -> str:
    """Clean HTML content to reduce token usage while preserving structure"""

    # 1. Remove script, style, and svg tags (heavy and non-functional for selectors)
    html_content = re.sub(r"<script.*?</script>", "", html_content, flags=re.DOTALL | re.IGNORECASE)
    html_content = re.sub(r"<style.*?</style>", "", html_content, flags=re.DOTALL | re.IGNORECASE)
    html_content = re.sub(r"<svg.*?</svg>", "[SVG]", html_content, flags=re.DOTALL | re.IGNORECASE)

    # 2. Remove common non-essential attributes to save tokens
    html_content = re.sub(r'\sstyle="[^"]*"', '', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'\son[a-z]+="[^"]*"', '', html_content, flags=re.IGNORECASE)

    # 3. Collapse whitespace
    html_content = re.sub(r'\s+', ' ', html_content)

    # 4. Truncate - 15,000 chars for good context without overloading
    return html_content[:15000]
