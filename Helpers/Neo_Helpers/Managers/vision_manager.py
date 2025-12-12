"""
Vision Manager for LeoBook
Handles screenshot capture and visual UI analysis for AI processing.
"""

import base64
from playwright.async_api import Page

from Helpers.utils import LOG_DIR
from Helpers.Neo_Helpers.Managers.api_key_manager import gemini_api_call_with_rotation
from Helpers.Neo_Helpers.Managers.prompt_manager import generate_dynamic_prompt
from google.generativeai.types import GenerationConfig


async def get_visual_ui_analysis(page: Page, context_key: str = "unknown") -> str:
    """
    Captures screenshot and performs visual UI analysis using Gemini AI.

    Args:
        page: Playwright Page object
        context_key: Context identifier for screenshot naming

    Returns:
        Analysis text from AI describing page elements
    """
    PAGE_LOG_DIR = LOG_DIR / "Page"
    files = list(PAGE_LOG_DIR.glob(f"*{context_key}.png"))

    if not files:
        print(f"    [VISION ERROR] No screenshot found for context: {context_key}")
        return ""

    # Get most recent screenshot
    png_file = max(files, key=lambda x: x.stat().st_mtime)
    print(f"    [VISION] Analyzing screenshot: {png_file.name}")

    try:
        image_data = {
            "mime_type": "image/png",
            "data": base64.b64encode(png_file.read_bytes()).decode("utf-8")
        }

        # Use page-specific prompt if available, fallback to general ui_analysis
        try:
            prompt = generate_dynamic_prompt(context_key, "vision")  # Specific prompt
        except ValueError:  # Prompt not found
            prompt = generate_dynamic_prompt("ui_analysis", "vision")  # Fallback

        response = await gemini_api_call_with_rotation(
            [prompt, image_data],
            generation_config=GenerationConfig(temperature=0.1)
        )

        print("    [VISION] Analysis complete.")
        return response.text if response.candidates else ""

    except Exception as e:
        print(f"    [VISION ERROR] Failed to analyze screenshot: {e}")
        return ""
