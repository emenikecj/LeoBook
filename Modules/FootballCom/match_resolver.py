# match_resolver.py: Intelligent match resolution using Google GenAI (GrokMatcher)
# Falls back to fuzzy matching if API is unavailable.
# Updated to use 'google.genai' (v2025 deprecation fix)

import os
from typing import List, Dict, Optional, Tuple
from Levenshtein import distance

# Try importing Google GenAI (New Package)
try:
    from google import genai
    from google.genai import types
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

class GrokMatcher:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.use_llm = HAS_GEMINI and bool(self.api_key)
        
        if self.use_llm:
            try:
                # Initialize new Client
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                print(f"    [GrokMatcher] Failed to initialize GenAI Client: {e}. Falling back to Fuzzy.")
                self.use_llm = False

    async def resolve(self, fs_name: str, fb_matches: List[Dict]) -> Tuple[Optional[Dict], float]:
        """
        Resolves a Flashscore match name against a list of Football.com matches.
        Returns (best_match_dict, score).
        """
        # Quick exact/fuzzy pre-filter to avoid API costs limitations
        best_fuzzy, fuzzy_score = self._fuzzy_resolve(fs_name, fb_matches)
        if fuzzy_score > 90: # Slightly lower threshold for raw Levenshtein score mapping
            return best_fuzzy, fuzzy_score

        if not self.use_llm:
            return best_fuzzy, fuzzy_score

        # Use LLM for difficult cases
        return await self._llm_resolve(fs_name, fb_matches, best_fuzzy, fuzzy_score)

    def _fuzzy_resolve(self, fs_name: str, fb_matches: List[Dict]) -> Tuple[Optional[Dict], float]:
        best_match = None
        min_distance = 999
        target = fs_name.lower()
        
        for m in fb_matches:
            candidate = f"{m.get('home_team')} vs {m.get('away_team')}".lower()
            dist = distance(target, candidate)
            if dist < min_distance:
                min_distance = dist
                best_match = m
        
        # Convert distance to a pseudo-score (0-100)
        # Score = 100 - (dist / max_len * 100)
        max_len = max(len(target), 1)
        score = max(0, 100 - (min_distance / max_len * 100))
                
        return best_match, score

    async def _llm_resolve(self, fs_name: str, fb_matches: List[Dict], fallback_match, fallback_score) -> Tuple[Optional[Dict], float]:
        """Call Gemini (google.genai) to pick the best match."""
        candidates = [f"{m.get('home_team')} vs {m.get('away_team')}" for m in fb_matches]
        
        prompt_text = (
            f"I have a football match named: '{fs_name}'.\n"
            f"Which of the following options represents the same match? Return ONLY the exact option string. "
            f"If none match clearly, return 'None'.\n\n"
            f"Options:\n" + "\n".join([f"- {c}" for c in candidates])
        )
        
        try:
            # Synchronous call via thread (Playwright async wrapper)
            import asyncio
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model="gemini-3-flash", # Using requested faster model
                contents=prompt_text
            )
            
            answer = response.text.strip().lower() if response.text else ""
            
            if "none" in answer or not answer:
                return fallback_match, fallback_score
            
            # Find which candidate matched the answer
            for i, cand in enumerate(candidates):
                if cand.lower() in answer or answer in cand.lower():
                    return fb_matches[i], 99.0
            
            return fallback_match, fallback_score
            
        except Exception as e:
            print(f"    [GrokMatcher] LLM specific error: {e}")
            return fallback_match, fallback_score
