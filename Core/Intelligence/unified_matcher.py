# unified_matcher.py: unified_matcher.py: Module for Core — Intelligence (AI Engine).
# Part of LeoBook Core — Intelligence (AI Engine)
#
# Classes: UnifiedBatchMatcher

"""
Unified Batch Matcher - v7 (Prompt Fix + No-Match Handling + Data Validation)
High-reliability batch matching with your specified models.
"""

import os
import json
import asyncio
from typing import List, Dict, Optional, Any
from datetime import datetime
from .api_manager import unified_api_call
from .utils import clean_json_response
from Core.Intelligence.aigo_suite import AIGOSuite

class UnifiedBatchMatcher:
    def __init__(self):
        self.chunk_size = 8  # Safe for token limits

    @AIGOSuite.aigo_retry(max_retries=2, delay=2.0, use_aigo=False)
    async def match_batch(self, date: str, predictions: List[Dict], site_matches: List[Dict]) -> Dict[str, str]:
        all_results = {}
        predictions = sorted(predictions, key=lambda x: x.get('fixture_id', ''))
        total_chunks = (len(predictions) + self.chunk_size - 1) // self.chunk_size
        
        print(f"  [AI Matcher] Processing {len(predictions)} predictions in {total_chunks} chunks (size {self.chunk_size})...")

        if not site_matches or all(m.get('home') == 'None' or m.get('away') == 'None' for m in site_matches):
            print("  [AI Matcher] No valid site matches for date – skipping batch")
            return {}

        for i in range(0, len(predictions), self.chunk_size):
            chunk_preds = predictions[i:i + self.chunk_size]
            chunk_idx = (i // self.chunk_size) + 1
            print(f"  [AI Matcher] Chunk {chunk_idx}/{total_chunks} ({len(chunk_preds)} items)...")
            
            chunk_result = await self._process_single_chunk(date, chunk_preds, site_matches)
            if chunk_result:
                all_results.update(chunk_result)
                print(f"  [AI Matcher] Chunk {chunk_idx} matched {len(chunk_result)} fixtures.")
            else:
                print(f"  [AI Matcher] Chunk {chunk_idx} returned no matches.")

        print(f"  [AI Matcher] Final: {len(all_results)}/{len(predictions)} matched")
        return all_results

    @AIGOSuite.aigo_retry(max_retries=2, delay=2.0)
    async def _process_single_chunk(self, date: str, predictions: List[Dict], site_matches: List[Dict]) -> Dict[str, str]:
        prompt = self._build_improved_prompt(date, predictions, site_matches)
        
        try:
            print(f"    [AI Chunk] Requesting AI Match Resolution...")
            response = await unified_api_call(
                prompt,
                generation_config={"temperature": 0.0, "response_mime_type": "application/json"}
            )
            
            if response and hasattr(response, 'text') and response.text:
                result = response.text
                print(f"    [AI Raw Response] {result[:3000]}...")  # Debug
                parsed = self._robust_parse(result)
                if parsed is not None:
                    print(f"    [AI Success] Parsed {len(parsed)} valid matches.")
                    return parsed
            
            print(f"    [AI] No valid response or empty result.")
        except Exception as e:
            print(f"    [AI Exception] Chunk matching failed: {e}")

        print("  [AI] Matching failed for chunk.")
        return {}

    def _build_improved_prompt(self, date: str, predictions: List[Dict], site_matches: List[Dict]) -> str:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S WAT")
        
        pred_summary = [f"{p.get('fixture_id')}: {p.get('home_team')} vs {p.get('away_team')} at {p.get('match_time')} ({p.get('date')})" for p in predictions]
        site_summary = [f"{s.get('home')} vs {s.get('away')} at {s.get('time')} ({s.get('date')}) - URL: {s.get('url')}" for s in site_matches]

    

        prompt = f"""You are a 100% precise fixture matcher for betting.
Current time: {now_str} (WAT/Nigeria)
Target date: {date}

TASK: Return JSON ONLY: {{"fixture_id": "url"}} for matches with >80% confidence.
If no match for a fixture_id, do NOT include it.
If no valid matches at all, return empty object {{}}.

STRICT RULES:
1. Match ONLY if teams are the same (ignore minor suffixes like FC, SC, Utd).
2. Time must be within 1 hour (discard if started/finished/postponed using current time).
3. Discard if league differs significantly.
4. Allow obvious equivalents (e.g. "Fatih Karagumruk" = "Karagumruk").
5. Output MUST be valid JSON object. NO markdown, NO text, NO explanations.

Few-shot examples:
Input: PRED: "Liverpool vs Man Utd at 20:00" SITE: "Liverpool FC vs Manchester United at 20:00" → {{"Liverpool_fixture": "https://..."}}
Input: PRED: "Arsenal vs Chelsea at 15:00" SITE: "Arsenal U21 vs Chelsea U21 at 15:00" → {{}} (discard - U21)
Input: PRED: "Real Madrid vs Barcelona at 21:00" SITE: no match → {{}}

PREDICTIONS:
{'\n'.join(pred_summary)}

SITE_MATCHES:
{'\n'.join(site_summary)}

RESPONSE: Valid JSON only.
"""
        return prompt



    def _robust_parse(self, text: str) -> Optional[Dict[str, str]]:
        if not text:
            return None

        cleaned_json = clean_json_response(text)
        try:
            parsed = json.loads(cleaned_json)
            if isinstance(parsed, dict):
                # Filter invalid entries
                valid = {k: v for k, v in parsed.items() if k and v and isinstance(v, str) and v.startswith("http")}
                if valid:
                    return valid
                else:
                    print("  [Parse] Filtered empty/invalid entries – returning {}")
                    return {}
        except json.JSONDecodeError as e:
            print(f"  [Parse Error] JSON decode failed via clean_json_response: {e}")

        # Manual fallback
        import re
        matches = re.findall(r'"(\w+)":\s*"([^"]+)"', text)
        if matches:
            valid = {k: v for k, v in dict(matches).items() if v.startswith("http")}
            if valid:
                return valid
            else:
                print("  [Parse] Manual fallback found no valid URLs")
                return {}

        print(f"  [Parse Fail] Raw: {text[:200]}...")
        return {}