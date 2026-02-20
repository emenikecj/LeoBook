# llm_matcher.py: llm_matcher.py: Semantic team name matching using LLMs.
# Part of LeoBook Core — Intelligence (AI Engine)
#
# Classes: SemanticMatcher

import requests
import json
import os
import asyncio
from typing import Optional, Dict

class SemanticMatcher:
    def __init__(self, model: str = 'google/gemini-2.5-flash'):
        """
        Initialize the SemanticMatcher. Strict OpenRouter usage.
        """
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY")
        
        if not self.openrouter_key:
            raise ValueError("OPENROUTER_API_KEY not found in .env. Local server is disabled.")

        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.model = os.getenv("OPENROUTER_MODEL", model)
        print(f"  [Matcher] Using OpenRouter API (Model: {self.model})")
            
        self.timeout = int(os.getenv("LLM_TIMEOUT", "60"))
        self.cache = {}

    async def is_match(self, desc1: str, desc2: str, league: Optional[str] = None) -> Optional[Dict]:
        """
        Determines if two match descriptions refer to the same football fixture.
        Returns a dict with 'is_match' (bool) and 'confidence' (int 0-100).
        """
        cache_key = f"{desc1}|{desc2}|{league or ''}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        context = ""
        if league:
            context = f"Both matches are in the league/competition: {league}. "

        prompt = (
            f"You are a precise sports betting matcher. Analyze if these two match descriptions refer to the EXACT SAME fixture.\n\n"
            f"Prediction: {desc1}\n"
            f"Site Candidate: {desc2}\n"
            f"{context}\n"
            f"Rules:\n"
            f"1. Ignore minor name variations (e.g. 'Fatih Karagumruk' = 'Karagumruk').\n"
            f"2. Ignore 'Istanbul' vs no 'Istanbul'.\n"
            f"3. Reject if league, date, or home/away order differs meaningfully.\n"
            f"4. Be strict about team identities.\n\n"
            f"Response MUST be valid JSON in this format: {{\"is_match\": bool, \"confidence\": int, \"reason\": string}}"
        )

        headers = {}
        if self.openrouter_key:
            headers = {
                "Authorization": f"Bearer {self.openrouter_key}",
                "HTTP-Referer": "https://github.com/emechijam/LeoBook",
                "X-Title": "LeoBook Matcher"
            }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a precise sports betting analyzer. You only speak JSON."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.0,
            "max_tokens": 150,
            # "response_format": {"type": "json_object"} # Commented out for broader compatibility
        }

        try:
            def _do_request():
                return requests.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout
                )

            response = await asyncio.to_thread(_do_request)
            response.raise_for_status()

            data = response.json()
            content = data['choices'][0]['message']['content'].strip()
            
            # Robust JSON parsing
            try:
                # Find JSON block if model talked outside it
                if "{" in content:
                    content = content[content.find("{"):content.rfind("}")+1]
                
                result = json.loads(content)
                
                # Normalize types
                if 'is_match' in result:
                    result['is_match'] = bool(result['is_match'])
                if 'confidence' in result:
                    result['confidence'] = int(result['confidence'])
                
                self.cache[cache_key] = result
                return result
            except (json.JSONDecodeError, ValueError, KeyError) as parse_error:
                print(f"  [LLM Matcher] JSON Parse Error: {parse_error}. Content: {content[:100]}...")
                # Fallback to simple yes/no detection if JSON fails
                content_lower = content.lower()
                simple_result = {
                    "is_match": "true" in content_lower or "yes" in content_lower,
                    "confidence": 70, # Lower confidence for malformed response
                    "reason": "fallback_parsing"
                }
                self.cache[cache_key] = simple_result
                return simple_result

        except Exception as e:
            print(f"  [LLM Matcher Error] {e}")
            return None
