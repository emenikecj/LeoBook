# match_resolver.py: match_resolver.py: Intelligent match resolution using Google GenAI (GrokMatcher)
# Part of LeoBook Modules — Football.com
#
# Classes: GrokMatcher

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
        self.use_llm = HAS_GEMINI
        if not self.use_llm:
            print("    [GrokMatcher] google-genai not available. Falling back to Fuzzy.")

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
        """Call Gemini via LLMHealthManager for multi-key/model rotation."""
        from Core.Intelligence.llm_health_manager import health_manager
        await health_manager.ensure_initialized()

        candidates = [f"{m.get('home_team')} vs {m.get('away_team')}" for m in fb_matches]
        
        prompt_text = (
            f"I have a football match named: '{fs_name}'.\n"
            f"Which of the following options represents the same match? Return ONLY the exact option string. "
            f"If none match clearly, return 'None'.\n\n"
            f"Options:\n" + "\n".join([f"- {c}" for c in candidates])
        )
        
        # Use DESCENDING chain (intelligence-critical task)
        model_chain = health_manager.get_model_chain("aigo")

        for model_name in model_chain:
            api_key = health_manager.get_next_gemini_key(model=model_name)
            if not api_key:
                continue
            try:
                import asyncio
                client = genai.Client(api_key=api_key)
                response = await asyncio.to_thread(
                    client.models.generate_content,
                    model=model_name,
                    contents=prompt_text
                )
                
                answer = response.text.strip().lower() if response.text else ""
                
                if "none" in answer or not answer:
                    return fallback_match, fallback_score
                
                for i, cand in enumerate(candidates):
                    if cand.lower() in answer or answer in cand.lower():
                        return fb_matches[i], 99.0
                
                return fallback_match, fallback_score
                
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    health_manager.on_gemini_429(api_key, model=model_name)
                    continue  # Try next model
                elif "403" in err_str:
                    health_manager.on_gemini_403(api_key)
                    continue
                print(f"    [GrokMatcher] LLM error on {model_name}: {e}")
                break

        return fallback_match, fallback_score
