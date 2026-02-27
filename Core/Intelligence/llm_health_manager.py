# llm_health_manager.py: Adaptive LLM provider health-check and routing.
# Part of LeoBook Core — Intelligence (AI Engine)
#
# Classes: LLMHealthManager
# Called by: api_manager.py, build_search_dict.py

"""
Multi-key, multi-model LLM health manager.

- Grok: single key (GROK_API_KEY)
- Gemini: comma-separated keys (GEMINI_API_KEY=key1,key2,...,key14)
  Round-robins through active keys AND models to maximize free-tier quota.

Model Chains (Feb 2026 free-tier rate limits per key):
  gemini-2.5-pro           5 RPM /  100 RPD  (best reasoning)
  gemini-3-flash-preview   5 RPM /   20 RPD  (frontier preview)
  gemini-2.5-flash        10 RPM /  250 RPD  (balanced)
  gemini-2.0-flash        15 RPM / 1500 RPD  (high throughput)
  gemini-2.5-flash-lite   15 RPM / 1000 RPD  (cheapest)

DESCENDING = pro-first (AIGO predictions, match analysis)
ASCENDING  = lite-first (search-dict metadata enrichment)
"""

import os
import time
import asyncio
import requests
from dotenv import load_dotenv

load_dotenv()

PING_INTERVAL = 900  # 15 minutes


class LLMHealthManager:
    """Singleton manager with multi-key, multi-model Gemini rotation."""

    _instance = None
    _lock = asyncio.Lock()

    # ── Model Chains ──────────────────────────────────────────
    # DESCENDING: max intelligence first (AIGO / predictions)
    # gemini-2.5-flash-lite excluded — reserved for SearchDict
    MODELS_DESCENDING = [
        "gemini-2.5-pro",
        "gemini-3-flash-preview",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
    ]

    # ASCENDING: max throughput first (search-dict / bulk enrichment)
    # gemini-2.5-pro excluded — reserved for AIGO
    MODELS_ASCENDING = [
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash",
        "gemini-2.5-flash",
        "gemini-3-flash-preview",
    ]

    # Default model for health-check pings (cheapest)
    PING_MODEL = "gemini-2.5-flash-lite"

    GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
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
            # Per-model exhausted keys (model_name -> set of exhausted keys)
            cls._instance._model_exhausted_keys = {}
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

    def get_model_chain(self, context: str = "aigo") -> list:
        """
        Returns the model priority chain for the given context.
        
        Args:
            context: "aigo" for DESCENDING (predictions/analysis),
                     "search_dict" for ASCENDING (bulk enrichment).
        """
        if context == "search_dict":
            return list(self.MODELS_ASCENDING)
        return list(self.MODELS_DESCENDING)

    def get_next_gemini_key(self, model: str = None) -> str:
        """
        Round-robin through active Gemini keys, skipping keys exhausted for
        the given model.
        """
        pool = self._gemini_active if self._gemini_active else self._gemini_keys
        if not pool:
            return ""

        exhausted = self._model_exhausted_keys.get(model, set()) if model else set()
        available = [k for k in pool if k not in exhausted]

        if not available:
            # All keys exhausted for this model — return empty to trigger model downgrade
            return ""

        key = available[self._gemini_index % len(available)]
        self._gemini_index += 1
        return key

    def on_gemini_429(self, failed_key: str, model: str = None):
        """
        Called when a Gemini key hits 429 for a specific model.
        Marks the key as exhausted for that model (not globally).
        """
        if model:
            if model not in self._model_exhausted_keys:
                self._model_exhausted_keys[model] = set()
            self._model_exhausted_keys[model].add(failed_key)
            remaining = len([k for k in (self._gemini_active or self._gemini_keys)
                           if k not in self._model_exhausted_keys[model]])
            print(f"    [LLM Health] Key ...{failed_key[-4:]} exhausted for {model}. "
                  f"{remaining} keys remaining for this model.")
            if remaining == 0:
                print(f"    [LLM Health] ⚠ All keys exhausted for {model} — will downgrade model.")
        else:
            # Legacy: remove from active pool entirely
            if failed_key in self._gemini_active:
                self._gemini_active.remove(failed_key)
                remaining = len(self._gemini_active)
                print(f"    [LLM Health] Gemini key rotated out (429). {remaining} keys remaining.")
                if remaining == 0:
                    print(f"    [LLM Health] ⚠ All {len(self._gemini_keys)} Gemini keys exhausted!")

    def on_gemini_403(self, failed_key: str):
        """Called when a Gemini key hits 403. Permanently remove from ALL pools."""
        if failed_key in self._gemini_active:
            self._gemini_active.remove(failed_key)
        if failed_key in self._gemini_keys:
            self._gemini_keys.remove(failed_key)
        print(f"    [LLM Health] Gemini key permanently removed (403 Forbidden). "
              f"{len(self._gemini_active)} active, {len(self._gemini_keys)} total.")

    def reset_model_exhaustion(self):
        """Reset per-model exhaustion tracking (call at start of each cycle)."""
        self._model_exhausted_keys.clear()

    # ── Internals ───────────────────────────────────────────────

    async def _ping_all(self):
        """Ping Grok + sample Gemini keys."""
        print("  [LLM Health] Pinging providers...")

        # Parse Gemini keys
        raw = os.getenv("GEMINI_API_KEY", "")
        self._gemini_keys = [k.strip() for k in raw.split(",") if k.strip()]

        # Reset per-model exhaustion on re-ping
        self._model_exhausted_keys.clear()

        # Ping Grok
        grok_key = os.getenv("GROK_API_KEY", "")
        self._grok_active = await self._ping_key("Grok", self.GROK_API_URL, self.GROK_MODEL, grok_key) if grok_key else False
        tag = "✓ Active" if self._grok_active else "✗ Inactive"
        print(f"  [LLM Health] Grok: {tag}")

        # Ping Gemini keys (sample 3 to avoid wasting quota)
        if self._gemini_keys:
            sample_indices = list({0, len(self._gemini_keys) // 2, len(self._gemini_keys) - 1})
            sample_results = []
            for idx in sample_indices:
                alive = await self._ping_key("Gemini", self.GEMINI_API_URL, self.PING_MODEL, self._gemini_keys[idx])
                sample_results.append(alive)

            if any(sample_results):
                self._gemini_active = list(self._gemini_keys)
                print(f"  [LLM Health] Gemini: ✓ Active ({len(self._gemini_keys)} keys, "
                      f"{len(self.MODELS_DESCENDING)} models available)")
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
