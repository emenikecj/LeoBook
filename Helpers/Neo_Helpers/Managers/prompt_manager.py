"""
Prompt Manager for LeoBook
Handles loading and serving dynamic AI prompts from organized text files.
Supports page-specific and function-specific prompt retrieval.
"""

import os
from pathlib import Path
from typing import Optional

# Prompts directory
PROMPTS_DIR = Path("Helpers/Neo_Helpers/Prompts")


def get_prompt(page_context: str, function: Optional[str] = None) -> str:
    """
    Retrieves the appropriate prompt based on page context and function.

    Args:
        page_context: Page type (e.g., 'fs_h2h_tab', 'fb_match_page')
        function: Specific function if needed (e.g., 'vision', 'mapping')

    Returns:
        The full prompt text from the corresponding file

    Priority:
    1. {page_context}_{function}.txt if function specified
    2. {page_context}.txt if exists
    3. generic.txt as fallback
    """
    if not PROMPTS_DIR.exists():
        raise FileNotFoundError(f"Prompts directory not found: {PROMPTS_DIR}")

    # Try specific prompt first
    if function:
        specific_file = PROMPTS_DIR / f"{page_context}_{function}.txt"
        if specific_file.exists():
            return _load_prompt_file(specific_file)

    # Try general page prompt
    page_file = PROMPTS_DIR / f"{page_context}.txt"
    if page_file.exists():
        return _load_prompt_file(page_file)

    # Try generic fallback
    generic_file = PROMPTS_DIR / "generic.txt"
    if generic_file.exists():
        return _load_prompt_file(generic_file)

    # No prompt found
    raise ValueError(f"No prompt found for page_context='{page_context}', function='{function}'")


def list_available_prompts() -> dict:
    """Returns a dictionary of all available prompts."""
    prompts = {}
    for file_path in PROMPTS_DIR.glob("*.txt"):
        key = file_path.stem  # filename without extension
        prompts[key] = str(file_path)
    return prompts


def _load_prompt_file(file_path: Path) -> str:
    """Loads and returns the content of a prompt file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if not content:
            raise ValueError(f"Prompt file is empty: {file_path}")
        return content
    except Exception as e:
        raise IOError(f"Failed to load prompt file {file_path}: {e}")


def generate_dynamic_prompt(base_context: str, function: str, **kwargs) -> str:
    """
    Generates a dynamic prompt by combining base prompt with additional context.

    Args:
        base_context: Base page context
        function: Function type
        **kwargs: Dynamic parameters to insert into the prompt

    Returns:
        Customized prompt with dynamic data inserted
    """
    base_prompt = get_prompt(base_context, function)

    # Insert dynamic data into placeholders
    for key, value in kwargs.items():
        placeholder = f"{{{key}}}"
        if placeholder in base_prompt:
            base_prompt = base_prompt.replace(placeholder, str(value))

    return base_prompt
