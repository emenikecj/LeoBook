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
    Uses google-genai SDK v1.64+ (Client-based API).
    Accepts optional api_key kwarg for multi-key rotation.
    """
    gemini_api_key = kwargs.get('api_key') or os.getenv("GEMINI_API_KEY", "").split(",")[0].strip()
    if not gemini_api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")

    import google.genai as genai
    from google.genai import types

    client = genai.Client(api_key=gemini_api_key)

    # 1. Parse Input (Text + Images)
    contents = []

    if isinstance(prompt_content, str):
        contents.append(types.Part.from_text(text=prompt_content))
    elif isinstance(prompt_content, list):
        for item in prompt_content:
            if isinstance(item, str):
                contents.append(types.Part.from_text(text=item))
            elif isinstance(item, dict):
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
                    contents.append(types.Part.from_bytes(
                        data=raw_bytes,
                        mime_type="image/png"
                    ))

    # 2. Build config
    config_kwargs = {}
    if generation_config:
        if hasattr(generation_config, 'temperature'):
            config_kwargs['temperature'] = generation_config.temperature
        elif isinstance(generation_config, dict) and 'temperature' in generation_config:
            config_kwargs['temperature'] = generation_config['temperature']

        mime = None
        if hasattr(generation_config, 'response_mime_type'):
            mime = generation_config.response_mime_type
        elif isinstance(generation_config, dict):
            mime = generation_config.get('response_mime_type')
        if mime:
            config_kwargs['response_mime_type'] = mime

    gen_config = types.GenerateContentConfig(**config_kwargs) if config_kwargs else None

    # 3. Execute Request
    def _make_gemini_request():
        return client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config=gen_config,
        )

    response = await asyncio.to_thread(_make_gemini_request)

    # Wrap response to match expected interface
    class MockGeminiResponse:
        def __init__(self, content):
            self.text = content

    return MockGeminiResponse(response.text)


async def unified_api_call(prompt_content, generation_config=None, **kwargs):
    """
    Unified API call with adaptive provider routing, multi-key Gemini rotation,
    and auto-fallback. Uses LLMHealthManager for health and key management.
    """
    from .llm_health_manager import health_manager

    # Ensure health check has run (pings every 15 min)
    await health_manager.ensure_initialized()
    ordered = health_manager.get_ordered_providers()

    last_error = None
    for provider_name in ordered:
        # Skip providers known to be inactive
        if not health_manager.is_provider_active(provider_name):
            print(f"    [AI] Skipping {provider_name} (inactive per health check)")
            continue

        if provider_name == "Gemini":
            # Multi-key rotation: try up to 3 different keys on 429
            max_key_retries = min(3, len(health_manager._gemini_active or health_manager._gemini_keys))
            for key_attempt in range(max_key_retries):
                api_key = health_manager.get_next_gemini_key()
                if not api_key:
                    break
                try:
                    key_suffix = api_key[-4:]
                    print(f"    [AI] Attempting Gemini (key ...{key_suffix})...")
                    response = await gemini_api_call(prompt_content, generation_config, api_key=api_key)
                    if response and hasattr(response, 'text') and response.text:
                        return response
                except Exception as e:
                    last_error = e
                    err_str = str(e)
                    if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                        health_manager.on_gemini_429(api_key)
                        print(f"    [AI] Gemini key ...{key_suffix} rate-limited, rotating...")
                        await asyncio.sleep(1)
                        continue
                    else:
                        print(f"    [AI WARNING] Gemini failed: {e}")
                        break  # Non-429 error, don't retry with different key

        elif provider_name == "Grok":
            try:
                print(f"    [AI] Attempting with Grok...")
                response = await grok_api_call(prompt_content, generation_config, **kwargs)
                if response and hasattr(response, 'text') and response.text:
                    return response
            except Exception as e:
                last_error = e
                print(f"    [AI WARNING] Grok failed: {e}")

    # All-inactive fallback: try Grok as last resort
    if not health_manager.is_provider_active("Grok"):
        try:
            print(f"    [AI] Last-resort attempt with Grok...")
            response = await grok_api_call(prompt_content, generation_config, **kwargs)
            if response and hasattr(response, 'text') and response.text:
                return response
        except Exception as e:
            last_error = e

    raise ValueError(f"All AI providers failed. Last error: {last_error}")