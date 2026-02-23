# api_manager.py: Manages AI API interactions (Grok, Gemini Fallback).
# Part of LeoBook Core — Intelligence (AI Engine)
#
# Functions: unified_api_call(), grok_api_call(), gemini_api_call()

import os
import requests
import json
import base64
import asyncio

# AI API configurations
GROK_API_URL = "https://api.x.ai/v1/chat/completions"


async def grok_api_call(prompt_content, generation_config=None, **kwargs):
    """
    Calls Grok API for AI analysis (vision and text).
    Uses asyncio.to_thread to keep the event loop running during the blocking request.
    """
    grok_api_key = os.getenv("GROK_API_KEY")
    if not grok_api_key:
        raise ValueError("GROK_API_KEY environment variable not set")

    # 1. Parse Input (Text + Images)
    message_content = []

    if isinstance(prompt_content, list):
        for item in prompt_content:
            if isinstance(item, str):
                message_content.append({"type": "text", "text": item})
            elif isinstance(item, dict):
                b64_data = None
                if "inline_data" in item:
                    b64_data = item["inline_data"].get("data")
                elif "data" in item:
                    b64_data = item["data"]
                    if isinstance(b64_data, bytes):
                        b64_data = base64.b64encode(b64_data).decode('utf-8')
                        
                if b64_data:
                    message_content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{b64_data}"
                        }
                    })
    elif isinstance(prompt_content, str):
        message_content.append({"type": "text", "text": prompt_content})

    # 2. Parse Config (Temperature)
    temperature = 0
    response_format = None
    if generation_config:
        if hasattr(generation_config, 'temperature'):
            temperature = generation_config.temperature
        elif isinstance(generation_config, dict) and 'temperature' in generation_config:
            temperature = generation_config['temperature']
            
        if hasattr(generation_config, 'response_mime_type') and generation_config.response_mime_type == "application/json":
             response_format = {"type": "json_object"}
        elif isinstance(generation_config, dict) and generation_config.get('response_mime_type') == "application/json":
             response_format = {"type": "json_object"}

    # 3. Construct Payload
    messages_list = [
        {
            "role": "system",
            "content": "You are a helpful assistant that analyzes text and images."
        },
        {
            "role": "user",
            "content": message_content
        }
    ]
    payload = {
        "model": "grok-4-latest",
        "messages": messages_list,
        "temperature": temperature,
        "max_tokens": 4096,
        "stream": False
    }
    
    if response_format:
        payload["response_format"] = response_format

    # 4. Execute Request
    def _make_grok_request():
        headers = {
            "Authorization": f"Bearer {grok_api_key}",
            "Content-Type": "application/json"
        }
        return requests.post(GROK_API_URL, json=payload, headers=headers, timeout=180)

    response = await asyncio.to_thread(_make_grok_request)
    response.raise_for_status()

    data = response.json()
    content = data['choices'][0]['message']['content']

    # Wrap response to match Mock Leo AI object interface
    class MockLeoResponse:
        def __init__(self, content):
            self.text = content
            self.candidates = [
                type('MockCandidate', (), {
                    'content': type('MockContent', (), {
                        'parts': [type('MockPart', (), {'text': content})]
                    })
                })
            ]

    return MockLeoResponse(content)


async def gemini_api_call(prompt_content, generation_config=None, **kwargs):
    """
    Calls Google Gemini API for AI analysis.
    Uses asyncio.to_thread to keep the event loop running during the blocking request.
    """
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")

    # Configure Gemini
    import google.genai as genai
    genai.configure(api_key=gemini_api_key)
    model = genai.GenerativeModel('gemini-2.5-pro')

    # 1. Parse Input (Text + Images)
    contents = []

    if isinstance(prompt_content, str):
        contents.append(prompt_content)
    elif isinstance(prompt_content, list):
        for item in prompt_content:
            if isinstance(item, str):
                contents.append(item)
            elif isinstance(item, dict):
                import PIL.Image
                import io
                
                b64_data = None
                raw_bytes = None
                
                if "inline_data" in item:
                    b64_data = item["inline_data"].get("data")
                elif "data" in item:
                    data = item["data"]
                    if isinstance(data, bytes):
                        raw_bytes = data
                    else:
                        b64_data = data
                        
                if b64_data:
                    raw_bytes = base64.b64decode(b64_data)
                    
                if raw_bytes:
                    image = PIL.Image.open(io.BytesIO(raw_bytes))
                    contents.append(image)

    # 2. Execute Request
    def _make_gemini_request():
        return model.generate_content(contents, generation_config=generation_config)

    response = await asyncio.to_thread(_make_gemini_request)

    # Wrap response to match expected interface
    class MockGeminiResponse:
        def __init__(self, content):
            self.text = content

    return MockGeminiResponse(response.text)


async def unified_api_call(prompt_content, generation_config=None, **kwargs):
    """
    Unified API call with @aigo_retry (retries) and auto-fallback between providers.
    """
    from .aigo_suite import AIGOSuite
    
    @AIGOSuite.aigo_retry(max_retries=2, delay=2.0, use_aigo=False)
    async def _execute_with_fallback():
        print("    [AI] Attempting with primary model (xAI Grok)...")
        try:
            grok_response = await grok_api_call(prompt_content, generation_config, **kwargs)
            if grok_response and hasattr(grok_response, 'text') and grok_response.text:
                return grok_response
        except Exception as e:
            print(f"    [AI WARNING] Grok failed: {e}. Trying Gemini fallback...")
        
        print("    [AI] Attempting fallback with Google Gemini...")
        gemini_response = await gemini_api_call(prompt_content, generation_config, **kwargs)
        if gemini_response and hasattr(gemini_response, 'text') and gemini_response.text:
            return gemini_response
        
        raise ValueError("Both AI providers (Grok and Gemini) failed to provide a valid response.")

    return await _execute_with_fallback()