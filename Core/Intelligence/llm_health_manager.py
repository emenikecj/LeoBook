# llm_health_manager.py: Adaptive LLM provider health-check and routing.
# Part of LeoBook Core — Intelligence (AI Engine)
#
# Classes: LLMHealthManager
# Called by: api_manager.py, build_search_dict.py

"""
Multi-key aware LLM health manager.

- Grok: single key (GROK_API_KEY)
- Gemini: supports comma-separated keys (GEMINI_API_KEY=key1,key2,...,key14)
  Round-robins through active keys to maximize free-tier quota.

Pings every 15 minutes. 429 = active (throttled). 401/403 = dead key.
"""

import os
import time
import asyncio
import requests
from dotenv import load_dotenv

load_dotenv()

PING_INTERVAL = 900  # 15 minutes


class LLMHealthManager:
    """Singleton manager with multi-key Gemini rotation."""

    _instance = None
    _lock = asyncio.Lock()

    GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    GEMINI_MODEL = "gemini-2.5-flash"
    GROK_API_URL = "https://api.x.ai/v1/chat/completions"
    GROK_MODEL = "grok-4-latest"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._grok_active = False
            cls._instance._gemini_keys = []       # All parsed keys
            cls._instance._gemini_active = []     # Keys that passed ping
            cls._instance._gemini_index = 0       # Round-robin pointer
            cls._instance._last_ping = 0.0
            cls._instance._initialized = False
        return cls._instance

    # ── Public API ──────────────────────────────────────────────

    async def ensure_initialized(self):
        """Ping providers if we haven't yet or if the interval has elapsed."""
        now = time.time()
        if not self._initialized or (now - self._last_ping) >= PING_INTERVAL:
            async with self._lock:
                if not self._initialized or (time.time() - self._last_ping) >= PING_INTERVAL:
                    await self._ping_all()

    def get_ordered_providers(self) -> list:
        """Returns provider names ordered: active first, inactive last."""
        if not self._initialized:
            return ["Grok", "Gemini"]

        active = []
        inactive = []
        if self._grok_active:
            active.append("Grok")
        else:
            inactive.append("Grok")
        if self._gemini_active:
            active.append("Gemini")
        else:
            inactive.append("Gemini")
        return active + inactive

    def is_provider_active(self, name: str) -> bool:
        """Check if a specific provider has at least one active key."""
        if name == "Grok":
            return self._grok_active
        if name == "Gemini":
            return len(self._gemini_active) > 0
        return False

    def get_next_gemini_key(self) -> str:
        """Round-robin through active Gemini keys."""
        if not self._gemini_active:
            # Fallback: try all keys
            if self._gemini_keys:
                key = self._gemini_keys[self._gemini_index % len(self._gemini_keys)]
                self._gemini_index += 1
                return key
            return ""
        key = self._gemini_active[self._gemini_index % len(self._gemini_active)]
        self._gemini_index += 1
        return key

    def on_gemini_429(self, failed_key: str):
        """Called when a Gemini key hits 429. Remove from active pool temporarily."""
        if failed_key in self._gemini_active:
            self._gemini_active.remove(failed_key)
            remaining = len(self._gemini_active)
            print(f"    [LLM Health] Gemini key rotated out (429). {remaining} keys remaining.")
            if remaining == 0:
                print(f"    [LLM Health] ⚠ All {len(self._gemini_keys)} Gemini keys exhausted!")

    # ── Internals ───────────────────────────────────────────────

    async def _ping_all(self):
        """Ping Grok + all Gemini keys."""
        print("  [LLM Health] Pinging providers...")

        # Parse Gemini keys
        raw = os.getenv("GEMINI_API_KEY", "")
        self._gemini_keys = [k.strip() for k in raw.split(",") if k.strip()]

        # Ping Grok
        grok_key = os.getenv("GROK_API_KEY", "")
        self._grok_active = await self._ping_key("Grok", self.GROK_API_URL, self.GROK_MODEL, grok_key) if grok_key else False
        tag = "✓ Active" if self._grok_active else "✗ Inactive"
        print(f"  [LLM Health] Grok: {tag}")

        # Ping Gemini keys (sample 3 to avoid wasting quota on ping)
        if self._gemini_keys:
            # Test first, middle, and last key as representative sample
            sample_indices = list({0, len(self._gemini_keys) // 2, len(self._gemini_keys) - 1})
            sample_results = []
            for idx in sample_indices:
                alive = await self._ping_key("Gemini", self.GEMINI_API_URL, self.GEMINI_MODEL, self._gemini_keys[idx])
                sample_results.append(alive)

            if any(sample_results):
                # If any sample key works, assume all keys are valid (same account)
                self._gemini_active = list(self._gemini_keys)
                print(f"  [LLM Health] Gemini: ✓ Active ({len(self._gemini_keys)} keys loaded)")
            else:
                self._gemini_active = []
                print(f"  [LLM Health] Gemini: ✗ Inactive (all {len(self._gemini_keys)} keys failed)")
        else:
            self._gemini_active = []
            print("  [LLM Health] Gemini: ✗ No keys configured")

        self._last_ping = time.time()
        self._initialized = True

        if not self._grok_active and not self._gemini_active:
            print("  [LLM Health] ⚠ CRITICAL — All LLM providers are offline! User action required.")

    async def _ping_key(self, name: str, api_url: str, model: str, api_key: str) -> bool:
        """Ping a single API key. 200/429 = active, 401/403 = dead."""
        if not api_key:
            return False

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 5,
            "temperature": 0,
        }

        def _do_ping():
            try:
                resp = requests.post(api_url, headers=headers, json=payload, timeout=10)
                return resp.status_code in (200, 429)
            except Exception:
                return False

        return await asyncio.to_thread(_do_ping)


# Module-level singleton
health_manager = LLMHealthManager()
