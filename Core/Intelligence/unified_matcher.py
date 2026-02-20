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
import aiohttp
import re
from datetime import datetime
from typing import List, Dict, Optional

class UnifiedBatchMatcher:
    def __init__(self):
        self.grok_key = os.getenv("GROK_API_KEY")
        self.gemini_key = os.getenv("GOOGLE_API_KEY")
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY")
        
        self.timeout = aiohttp.ClientTimeout(total=180)  # 3 min
        self.max_retries = 3
        self.chunk_size = 8  # Safe for token limits

        self.grok_model = "grok-4-1-fast-reasoning"
        self.gemini_model = "gemini-3-flash"
        self.openrouter_model = "google/gemini-2.5-flash"

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

    async def _process_single_chunk(self, date: str, predictions: List[Dict], site_matches: List[Dict]) -> Dict[str, str]:
        prompt = self._build_improved_prompt(date, predictions, site_matches)
        
        rotation = [
            (self._call_grok, "Grok", self.grok_model),
            (self._call_gemini, "Gemini", self.gemini_model),
            (self._call_openrouter, "OpenRouter", self.openrouter_model)
        ]
        
        for call_func, model_name, model_id in rotation:
            if not (model_name == "Grok" and self.grok_key or
                    model_name == "Gemini" and self.gemini_key or
                    model_name == "OpenRouter" and self.openrouter_key):
                print(f"  [AI Skip] {model_name} key missing – skipping")
                continue

            for attempt in range(1, self.max_retries + 1):
                try:
                    print(f"    [AI Chunk] {model_name} ({model_id}) Attempt {attempt}...")
                    result = await call_func(prompt, model_id)
                    if result:
                        print(f"    [AI Raw Response] {result[:3000]}...")  # Debug
                        parsed = self._robust_parse(result)
                        if parsed:
                            print(f"    [AI Success] Parsed {len(parsed)} matches from {model_name}")
                            return parsed
                    else:
                        print(f"    [AI] {model_name} returned empty/null")
                except Exception as e:
                    print(f"    [AI Exception] {model_name} attempt {attempt}: {e}")
                    if attempt < self.max_retries:
                        await asyncio.sleep(5)
            print(f"    [AI] {model_name} exhausted retries")

        print("  [AI] All models failed for chunk")
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

    async def _call_grok(self, prompt: str, model: str) -> Optional[str]:
        url = "https://api.x.ai/v1/chat/completions"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.grok_key}"}
        payload = {
            "messages": [{"role": "user", "content": prompt}],
            "model": model,
            "temperature": 0.0,
            "max_tokens": 2048
        }
        return await self._make_api_call(url, headers, payload)

    async def _call_gemini(self, prompt: str, model: str) -> Optional[str]:
        url = f"https://generativelanguage.googleapis.com/v1/models/{model}:generateContent?key={self.gemini_key}"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        return await self._make_api_call(url, {}, payload)

    async def _call_openrouter(self, prompt: str, model: str) -> Optional[str]:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.openrouter_key}",
            "HTTP-Referer": "https://leo-book.com",
            "X-Title": "LeoBook Matcher"
        }
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "max_tokens": 2048
        }
        return await self._make_api_call(url, headers, payload)

    async def _make_api_call(self, url: str, headers: Dict, payload: Dict) -> Optional[str]:
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            try:
                async with session.post(url, headers=headers, json=payload) as resp:
                    text = await resp.text()
                    if resp.status in (200, 201):
                        data = json.loads(text)
                        if 'choices' in data and data['choices']:
                            return data['choices'][0]['message']['content']
                        elif 'candidates' in data and data['candidates']:
                            return data['candidates'][0]['content']['parts'][0]['text']
                    print(f"  [API Error] Status {resp.status} - {text[:200]}...")
                    return None
            except Exception as e:
                print(f"  [API Exception] {e}")
                return None

    def _robust_parse(self, text: str) -> Optional[Dict[str, str]]:
        text = text.strip()
        if not text:
            return None

        # Strip markdown/code blocks
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        # Find JSON block
        start = text.find('{')
        end = text.rfind('}') + 1
        if start != -1 and end > start:
            text = text[start:end]

        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                # Filter invalid entries
                valid = {k: v for k, v in parsed.items() if k and v and isinstance(v, str) and v.startswith("http")}
                if valid:
                    return valid
                else:
                    print("  [Parse] Filtered empty/invalid entries – returning {}")
                    return {}
        except json.JSONDecodeError as e:
            print(f"  [Parse Error] JSON decode failed: {e}")

        # Manual fallback
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