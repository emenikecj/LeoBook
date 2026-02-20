# api_manager.py: api_manager.py: Manages AI API interactions (Gemini, local Leo AI).
# Part of LeoBook Core — Intelligence (AI Engine)
#
# Functions: leo_api_call_with_rotation(), grok_api_call(), gemini_api_call_with_rotation(), ai_api_call()

import os
import requests
import json
import base64
import google.genai as genai

# Default fallback URL if env var is missing
DEFAULT_API_URL = "http://127.0.0.1:8080/v1/chat/completions"

# Grok API configuration
GROK_API_URL = "https://api.x.ai/v1/chat/completions"

import asyncio

async def leo_api_call_with_rotation(prompt_content, generation_config=None, **kwargs):
    """
    Redirects legacy calls to our local compatible Leo AI server (llama-server/Qwen3-VL).
    Uses asyncio.to_thread to keep the event loop running during the blocking request.
    """
    api_url = os.getenv("LLM_API_URL", DEFAULT_API_URL)

    # 1. Parse Input (Text + Images)
    message_content = []

    if isinstance(prompt_content, list):
        for item in prompt_content:
            if isinstance(item, str):
                message_content.append({"type": "text", "text": item})
            elif isinstance(item, dict) and "inline_data" in item:
                # Extract image data
                b64_data = item["inline_data"].get("data")
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
    temperature = 0.1
    if generation_config:
        if hasattr(generation_config, 'temperature'):
            temperature = generation_config.temperature
        elif isinstance(generation_config, dict) and 'temperature' in generation_config:
            temperature = generation_config['temperature']

    # 3. Construct Payload
    payload = {
        "model": "qwen2-vl", # Explicitly add model key
        "messages": [
            {
                "role": "user",
                "content": message_content
            }
        ],
        "temperature": temperature,
        "max_tokens": 1500, # More conservative to avoid context overflow
        "stream": False
    }

    # Note: 'response_format' is removed to avoid 400 errors.

    # 4. Execute with Retry for 503 (Loading Model)
    max_retries = 12
    retry_delay = 10 # seconds

    for attempt in range(max_retries):
        response = None
        try:
            def _make_request():
                return requests.post(api_url, json=payload, timeout=180)

            response = await asyncio.to_thread(_make_request)
            
            if response.status_code == 503:
                print(f"    [AI Bridge] Server is loading model (503). Retrying in {retry_delay}s... ({attempt+1}/{max_retries})")
                await asyncio.sleep(retry_delay)
                continue

            response.raise_for_status()
            
            data = response.json()
            ans = data['choices'][0]['message']['content']

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

            return MockLeoResponse(ans)

        except Exception as e:
            # Handle non-503 errors or final failure
            error_msg = str(e)
            if response is not None:
                if hasattr(response, 'text'):
                    error_msg += f" | Server Response: {response.text}"
            print(f"    [AI Bridge Error] Failed to connect to {api_url}: {error_msg}")
            return None
    
    print(f"    [AI Bridge Error] AI Server timed out after {max_retries * retry_delay}s of loading.")
    return None


async def grok_api_call(prompt_content, generation_config=None, **kwargs):
    """
    Calls Grok API for AI analysis (vision and text).
    Uses asyncio.to_thread to keep the event loop running during the blocking request.
    """
    grok_api_key = os.getenv("GROK_API_KEY")
    if not grok_api_key:
        print("    [GROK ERROR] GROK_API_KEY environment variable not set")
        return None

    # 1. Parse Input (Text + Images)
    message_content = []

    if isinstance(prompt_content, list):
        for item in prompt_content:
            if isinstance(item, str):
                message_content.append({"type": "text", "text": item})
            elif isinstance(item, dict) and "inline_data" in item:
                # Extract image data
                b64_data = item["inline_data"].get("data")
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
    if generation_config:
        if hasattr(generation_config, 'temperature'):
            temperature = generation_config.temperature
        elif isinstance(generation_config, dict) and 'temperature' in generation_config:
            temperature = generation_config['temperature']

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

    # 4. Execute Request
    response = None
    try:
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

    except Exception as e:
        error_msg = str(e)
        if response is not None:
            if hasattr(response, 'text'):
                error_msg += f" | Server Response: {response.text}"
        print(f"    [GROK ERROR] Failed to connect to Grok API: {error_msg}")
        return None


async def gemini_api_call_with_rotation(prompt_content, generation_config=None, **kwargs):
    """
    Calls Google Gemini API for AI analysis.
    Uses asyncio.to_thread to keep the event loop running during the blocking request.
    """
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        print("    [GEMINI ERROR] GEMINI_API_KEY environment variable not set")
        return None

    # Configure Gemini
    genai.configure(api_key=gemini_api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')

    # 1. Parse Input (Text + Images)
    contents = []

    if isinstance(prompt_content, str):
        contents.append(prompt_content)
    elif isinstance(prompt_content, list):
        for item in prompt_content:
            if isinstance(item, str):
                contents.append(item)
            elif isinstance(item, dict) and "mime_type" in item and "data" in item:
                # Image data
                import PIL.Image
                import io
                image_data = base64.b64decode(item["data"])
                image = PIL.Image.open(io.BytesIO(image_data))
                contents.append(image)

    # 2. Execute Request
    try:
        def _make_gemini_request():
            return model.generate_content(contents, generation_config=generation_config)

        response = await asyncio.to_thread(_make_gemini_request)

        # Wrap response to match expected interface
        class MockGeminiResponse:
            def __init__(self, content):
                self.text = content

        return MockGeminiResponse(response.text)

    except Exception as e:
        print(f"    [GEMINI ERROR] Failed to connect to Gemini API: {e}")
        return None


async def ai_api_call(prompt_content, generation_config=None, **kwargs):
    """
    Unified AI API call that switches between Leo (local) and Grok (cloud) based on USE_GROK_API env var.
    Defaults to Leo for backward compatibility.
    """
    use_grok = os.getenv("USE_GROK_API", "true").lower() == "true"

    if use_grok:
        print("    [AI] Using Grok API for analysis...")
        return await grok_api_call(prompt_content, generation_config, **kwargs)
    else:
        print("    [AI] Using local Leo AI for analysis...")
        return await leo_api_call_with_rotation(prompt_content, generation_config, **kwargs)