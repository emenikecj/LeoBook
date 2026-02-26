# llm_health_manager.py: Adaptive LLM provider health-check and routing.
# Part of LeoBook Core — Intelligence (AI Engine)
#
# Classes: LLMHealthManager
# Called by: api_manager.py, build_search_dict.py

"""
Pings Grok and Gemini every 15 minutes to determine which providers are alive.
Routes LLM calls to the active provider, skipping dead ones instantly.
If both are down, alerts the user.
"""

import os
import time
import asyncio
import requests
from dotenv import load_dotenv

load_dotenv()

PING_INTERVAL = 900  # 15 minutes


class LLMHealthManager:
    """Singleton manager that tracks LLM provider health via periodic pings."""

    _instance = None
    _lock = asyncio.Lock()

    # Provider registry
    PROVIDERS = {
        "Grok": {
            "api_url": "https://api.x.ai/v1/chat/completions",
            "model": "grok-4-1-fast-reasoning",
            "env_key": "GROK_API_KEY",
        },
        "Gemini": {
            "api_url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
            "model": "gemini-2.5-flash",
            "env_key": "GEMINI_API_KEY",
        },
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._status = {}       # {"Grok": True/False, "Gemini": True/False}
            cls._instance._last_ping = 0.0
            cls._instance._initialized = False
        return cls._instance

    # ── Public API ──────────────────────────────────────────────

    async def ensure_initialized(self):
        """Ping providers if we haven't yet or if the interval has elapsed."""
        now = time.time()
        if not self._initialized or (now - self._last_ping) >= PING_INTERVAL:
            async with self._lock:
                # Double-check inside lock
                if not self._initialized or (time.time() - self._last_ping) >= PING_INTERVAL:
                    await self._ping_all()

    def get_ordered_providers(self) -> list:
        """
        Returns provider names ordered: active ones first, inactive ones last.
        If no ping has run yet, returns default order ['Grok', 'Gemini'].
        """
        if not self._status:
            return ["Grok", "Gemini"]

        active = [name for name, alive in self._status.items() if alive]
        inactive = [name for name, alive in self._status.items() if not alive]
        return active + inactive

    def is_provider_active(self, name: str) -> bool:
        """Check if a specific provider is active."""
        return self._status.get(name, True)  # Default True if never pinged

    def get_provider_config(self, name: str) -> dict:
        """Returns full config for a provider including its API key."""
        base = self.PROVIDERS.get(name, {})
        return {
            "name": name,
            "api_key": os.getenv(base.get("env_key", "")),
            "api_url": base.get("api_url", ""),
            "model": base.get("model", ""),
        }

    # ── Internals ───────────────────────────────────────────────

    async def _ping_all(self):
        """Ping every provider with a tiny request to check health."""
        print("  [LLM Health] Pinging providers...")
        for name in self.PROVIDERS:
            alive = await self._ping_one(name)
            self._status[name] = alive
            tag = "✓ Active" if alive else "✗ Inactive"
            print(f"  [LLM Health] {name}: {tag}")

        self._last_ping = time.time()
        self._initialized = True

        # Alert if all dead
        if not any(self._status.values()):
            print("  [LLM Health] ⚠ CRITICAL — All LLM providers are offline! User action required.")

    async def _ping_one(self, name: str) -> bool:
        """
        Send a minimal request to check if the provider is reachable.
        
        Returns True (active) for: 200 OK, 429 Rate Limited (provider works, just throttled).
        Returns False (inactive) for: 401/403 Auth errors, connection failures, timeouts.
        """
        cfg = self.PROVIDERS[name]
        api_key = os.getenv(cfg["env_key"])
        if not api_key:
            return False

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": cfg["model"],
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 5,
            "temperature": 0,
        }

        def _do_ping():
            try:
                resp = requests.post(
                    cfg["api_url"], headers=headers, json=payload, timeout=10
                )
                # 200 = working, 429 = working but throttled (still active)
                if resp.status_code in (200, 429):
                    return True
                # 401/403 = auth failure (truly inactive)
                return False
            except Exception:
                return False

        return await asyncio.to_thread(_do_ping)


# Module-level singleton
health_manager = LLMHealthManager()
