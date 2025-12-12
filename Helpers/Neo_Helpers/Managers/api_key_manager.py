# api_key_manager.py
import os
import json
import asyncio
import atexit
from dotenv import load_dotenv

import google.generativeai as genai
from google.generativeai.types import GenerationConfig

load_dotenv()

class ApiKeyManager:
    """
    Manages a pool of Gemini API keys from environment variables.
    Handles loading, rotating, and providing the current key.
    """
    def __init__(self):
        self.keys = self._load_keys()
        self.current_key_index = 0
        self.exhausted_keys = set()
        self._load_state()
        if not self.keys:
            raise ValueError("No Google API keys found. Please set GOOGLE_API_KEYS in your .env file.")
        print(f"  [API Key] Loaded {len(self.keys)} keys. Starting with index {self.current_key_index}. Exhausted: {len(self.exhausted_keys)}")

    def _load_state(self):
        """Loads the state from a file."""
        state_file = "DB/auth/api_key_state.json"
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r') as f:
                    state = json.load(f)
                    self.current_key_index = state.get('last_index', 0)
                    self.exhausted_keys = set(state.get('exhausted', []))
            except Exception as e:
                print(f"  [API Key] Failed to load state: {e}")

    def _save_state(self):
        """Saves the current state to a file."""
        state_file = "DB/auth/api_key_state.json"
        state = {
            'last_index': self.current_key_index,
            'exhausted': list(self.exhausted_keys)
        }
        try:
            with open(state_file, 'w') as f:
                json.dump(state, f)
        except Exception as e:
            print(f"  [API Key] Failed to save state: {e}")

    def _load_keys(self) -> list[str]:
        """Loads keys from the GOOGLE_API_KEYS environment variable."""
        keys_str = os.getenv("GOOGLE_API_KEYS")
        if not keys_str:
            return []
        return [key.strip() for key in keys_str.split(',') if key.strip()]

    def get_current_key(self) -> str:
        """Returns the current API key."""
        return self.keys[self.current_key_index]

    def rotate_key(self) -> bool:
        """
        Rotates to the next non-exhausted key.
        If all keys are exhausted, resets exhausted list and starts from index 0.
        Returns True if a new key is available, False if reset to start.
        """
        print(f"  [API Key] Rotating from key index {self.current_key_index} due to quota limit.")
        self.exhausted_keys.add(self.current_key_index)

        # Find next non-exhausted key
        start_index = self.current_key_index
        while True:
            self.current_key_index = (self.current_key_index + 1) % len(self.keys)
            if self.current_key_index not in self.exhausted_keys:
                print(f"  [API Key] Switched to key index: {self.current_key_index}")
                self._save_state()
                return True
            if self.current_key_index == start_index:
                # All keys exhausted
                print("  [API Key Warning] All keys exhausted. Resetting and starting from index 0.")
                self.exhausted_keys.clear()
                self.current_key_index = 0
                self._save_state()
                return False

# Create a single, global instance to be used across the application
key_manager = ApiKeyManager()

# Register atexit handler to save state when program exits
atexit.register(key_manager._save_state)

async def gemini_api_call_with_rotation(prompt_content, generation_config, **kwargs):
    """
    A centralized wrapper for Gemini API calls that handles 429 errors by rotating API keys.
    """
    initial_key_index = key_manager.current_key_index
    while True:
        try:
            # Configure the API key for the current attempt
            current_key = key_manager.get_current_key()
            genai.configure(api_key=current_key)  # type: ignore
            model = genai.GenerativeModel("gemini-2.5-flash")  # type: ignore

            response = await model.generate_content_async(
                prompt_content,
                generation_config=generation_config,
                **kwargs # Pass through any extra arguments like safety_settings
            )
            return response

        except Exception as e: # Catch all exceptions
            # Check if the error is a quota error
            if "429" in str(e) and "quota" in str(e).lower():
                print(f"    [Gemini Error] Quota exceeded for key index {key_manager.current_key_index}.")

                # Rotate key and check if we've tried all keys
                if not key_manager.rotate_key(): # and key_manager.current_key_index == initial_key_index:
                    # We have tried all keys and are back to the start.
                    # Wait for a minute before trying the first key again.
                    print("    [API Key] All keys are rate-limited. Waiting for 60 seconds...")
                    await asyncio.sleep(180)
                # After rotating (or waiting), continue the loop to retry the request
                continue
            else:
                # It's a different, non-quota error, so we re-raise it to be handled by the caller.
                # This breaks the infinite loop.
                raise e
