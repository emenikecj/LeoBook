import os
import json
import asyncio
import aiohttp
from typing import List, Dict, Any, Optional
from datetime import datetime

class UnifiedBatchMatcher:
    def __init__(self):
        self.grok_key = os.getenv("GROK_API_KEY")
        self.gemini_key = os.getenv("GOOGLE_API_KEY")
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY")
        
        self.timeout = aiohttp.ClientTimeout(total=120)  # 2 minute timeout as requested
        self.max_retries = 3

    async def match_batch(self, date: str, predictions: List[Dict], site_matches: List[Dict]) -> Dict[str, str]:
        """
        Coordinates the batch matching process with rotation, using chunking to avoid LLM overload.
        """
        all_results = {}
        chunk_size = 20 # Conservative chunk size for stability
        
        # Sort predictions by fixture_id for consistent chunking
        predictions = sorted(predictions, key=lambda x: x.get('fixture_id', ''))
        total_chunks = (len(predictions) + chunk_size - 1) // chunk_size
        
        print(f"  [AI Matcher] Processing {len(predictions)} predictions in {total_chunks} chunks (Size: {chunk_size})...")

        for i in range(0, len(predictions), chunk_size):
            chunk_preds = predictions[i:i + chunk_size]
            chunk_idx = (i // chunk_size) + 1
            print(f"  [AI Matcher] Processing Chunk {chunk_idx}/{total_chunks} ({len(chunk_preds)} items)...")
            
            chunk_result = await self._process_single_chunk(date, chunk_preds, site_matches)
            if chunk_result:
                all_results.update(chunk_result)
                print(f"  [AI Matcher] Chunk {chunk_idx} matched {len(chunk_result)} fixtures.")
            else:
                 print(f"  [AI Matcher] Chunk {chunk_idx} failed to resolve any matches.")

        return all_results

    async def _process_single_chunk(self, date: str, predictions: List[Dict], site_matches: List[Dict]) -> Dict[str, str]:
        """Process a single chunk of predictions against ALL site matches."""
        prompt = self._build_batch_prompt(date, predictions, site_matches)
        
        # Define the rotation: (function, name)
        rotation = [
            (self._call_grok, "Grok"),
            (self._call_gemini, "Gemini"),
            (self._call_openrouter, "OpenRouter")
        ]
        
        for call_func, model_name in rotation:
            for attempt in range(1, self.max_retries + 1):
                try:
                    # print(f"    [AI Chunk] {model_name} Attempt {attempt}...")
                    result = await call_func(prompt)
                    if result is not None:
                        # Allow {} as a valid result
                        parsed = self._parse_response(result)
                        if isinstance(parsed, dict):
                            return parsed
                        else:
                            print(f"    [AI Error] {model_name} returned unparseable content. Raw start: {result[:50]}...")
                    else:
                        print(f"    [AI Error] {model_name} returned None (API Error).")
                except Exception as e:
                    print(f"    [AI Exception] {model_name} attempt {attempt} failed: {e}")
                    if attempt < self.max_retries:
                        await asyncio.sleep(2)
            
            print(f"    [AI Fail] {model_name} failed chunk after {self.max_retries} attempts. Rotating...")
            
        return {}

    def _build_batch_prompt(self, date: str, predictions: List[Dict], site_matches: List[Dict]) -> str:
        """Constructs the advanced batch prompt."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        pred_data = []
        for p in predictions:
            pred_data.append({
                "fixture_id": p.get('fixture_id'),
                "region_league": p.get('region_league'),
                "home_team": p.get('home_team'),
                "away_team": p.get('away_team'),
                "match_time": p.get('match_time'),
                "date": p.get('date')
            })
            
        site_data = []
        for s in site_matches:
            site_data.append({
                "url": s.get('url'),
                "league": s.get('league'),
                "home": s.get('home') or s.get('home_team'),
                "away": s.get('away') or s.get('away_team'),
                "time": s.get('time'),
                "date": s.get('date')
            })

        prompt = f"""You are a high-intelligence sports betting data synchronizer.
Current System Time: {now_str} (WAT - West Africa Time / Nigerian Time)
Target Date: {date}

TASK:
Match the fixtures from 'PREDICTIONS' to the exact same fixtures in 'SITE_MATCHES'. 
Return a mapping of 'fixture_id' from PREDICTIONS to the corresponding 'url' from SITE_MATCHES.

RULES:
1. STRICT MATCHING: Be EXTREMELY precise. Only match if you are "100% sure" the fixtures represent the exact same physical event (Team A vs Team B).
2. NIGERIAN TIME (WAT): All dates and times provided in 'PREDICTIONS' are in Nigerian Time (UTC+1). Use this as your reference for all comparisons.
3. TIME & STATUS FILTERING:
   - Perform a WEB SEARCH to verify the real-time status and kickoff time of each candidate match.
   - DISCARD any match that has already started or finished according to:
     a) The kickoff time and date provided in 'PREDICTIONS' (Predictions.csv data).
     b) The Current System Time ({now_str} WAT).
     c) Your real-time web search results.
   - If a match is LIVE, COMPLETED, or POSTPONED, it MUST be excluded.
   - Discard matches starting within the next 5 minutes as a safety buffer.
4. NO FUZZY OVERHEAD: Ignore minor spelling differences or team name suffixes (FC, SC, etc.).
5. NO PARTIALS: Only include mappings for matches found in BOTH datasets. Return {{}} if no matches qualify.

DATA:
--- PREDICTIONS (Source: predictions.csv) ---
{json.dumps(pred_data, indent=2)}

--- SITE_MATCHES (Source: Football.com) ---
{json.dumps(site_data, indent=2)}

RESPONSE FORMAT:
You MUST respond with a valid JSON object only. The keys should be 'fixture_id' and values should be the 'url'.
Example: {{"123456": "https://www.football.com/match/fixture-id"}}

Response:"""
        return prompt

    async def _call_grok(self, prompt: str) -> Optional[str]:
        if not self.grok_key: return None
        url = "https://api.x.ai/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.grok_key}"
        }
        payload = {
            "messages": [
                {"role": "system", "content": "You are a precise data matching assistant that only outputs JSON."},
                {"role": "user", "content": prompt}
            ],
            "model": "grok-4-1-fast-reasoning", # Note: using the model name from user request
            "stream": False,
            "temperature": 0
        }
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            try:
                async with session.post(url, headers=headers, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data['choices'][0]['message']['content']
                    print(f"    [Grok Error] Status: {resp.status} - {await resp.text()}")
                    return None
            except Exception as e:
                print(f"    [Grok Exception] {e}")
                return None

    async def _call_gemini(self, prompt: str) -> Optional[str]:
        if not self.gemini_key: return None
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash:generateContent?key={self.gemini_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json"}
        }
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            try:
                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data['candidates'][0]['content']['parts'][0]['text']
                    print(f"    [Gemini Error] Status: {resp.status} - {await resp.text()}")
                    return None
            except Exception as e:
                 print(f"    [Gemini Exception] {e}")
                 return None

    async def _call_openrouter(self, prompt: str) -> Optional[str]:
        if not self.openrouter_key: return None
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.openrouter_key}",
            "HTTP-Referer": "https://github.com/emechijam/LeoBook",
            "X-Title": "LeoBook Matcher"
        }
        payload = {
            "model": "google/gemini-2.5-flash",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0
        }
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            try:
                async with session.post(url, headers=headers, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data['choices'][0]['message']['content']
                    print(f"    [OpenRouter Error] Status: {resp.status} - {await resp.text()}")
                    return None
            except Exception as e:
                 print(f"    [OpenRouter Exception] {e}")
                 return None

    def _parse_response(self, text: str) -> Optional[Dict[str, str]]:
        """Extracts JSON from response, handling markdown blocks and extra text."""
        try:
            # 1. Try direct parse
            text = text.strip()
            if text.startswith("{") and text.endswith("}"):
                return json.loads(text)
            
            # 2. Extract from markdown code blocks
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            
            # 3. Last ditch search for first '{' and last '}'
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1:
                text = text[start:end+1]
                
            return json.loads(text.strip())
        except Exception as e:
            # Only print error if it's truly broken. 
            if '{' in text:
                print(f"  [AI Matcher Parse Error] {e} | Content Snippet: {text[:100]}...")
            return None
