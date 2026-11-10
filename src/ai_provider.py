import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("ai_provider")
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE_DIR / "data" / "ai_provider_config.json"

PROVIDERS = {
    "moonmath": {
        "name": "MoonMath Zro (Private Inference)",
        "base_url": "https://zro.moonmath.ai/v1",
        "default_model": "deepseek-v4.1-flash",
        "available_models": [
            "deepseek-v4.1-flash",
            "deepseek-v4-flash-0731",
            "glm-5.3-flash"
        ],
        "env_key": "MOONMATH_API_KEY",
        "docs_url": "https://zro.moonmath.ai",
        "requires_key": True
    },
    "apinex": {
        "name": "APInex (20M Free Tokens)",
        "base_url": "https://api.apinex.bond/v1",
        "default_model": "free/deepseek-v4.1-flash",
        "available_models": [
            "free/deepseek-v4.1-flash",
            "free/gemini-3.8-flash",
            "free/gpt-6-luna",
            "free/glm-5.3-flash",
            "free/qwen-3.8-max",
            "free/deepseek-v4-flash-0731"
        ],
        "env_key": "APINEX_API_KEY",
        "docs_url": "https://apinex.bond/overview",
        "requires_key": True
    },
    "openrouter": {
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "deepseek/deepseek-chat",
        "available_models": [
            "deepseek/deepseek-chat",
            "deepseek/deepseek-r1:free",
            "meta-llama/llama-3.3-70b-instruct",
            "google/gemini-2.0-flash-exp:free",
            "anthropic/claude-3.5-sonnet"
        ],
        "env_key": "OPENROUTER_API_KEY",
        "docs_url": "https://openrouter.ai",
        "requires_key": True
    },
    "kie": {
        "name": "Kie.ai",
        "base_url": "https://api.kie.ai/openai/v1",
        "default_model": "deepseek-v4-1-flash",
        "available_models": [
            "deepseek-v4-1-flash",
            "deepseek-chat"
        ],
        "env_key": "KIE_API_KEY",
        "docs_url": "https://kie.ai",
        "requires_key": True
    },
    "offline": {
        "name": "Offline Fallback (Zero Tokens)",
        "base_url": "",
        "default_model": "rule-based-dynamic",
        "available_models": ["rule-based-dynamic"],
        "env_key": "",
        "docs_url": "",
        "requires_key": False
    }
}

def load_ai_config() -> Dict[str, Any]:
    """Load AI provider settings from JSON config or environment defaults."""
    default_provider = "offline"
    if os.getenv("APINEX_API_KEY"):
        default_provider = "apinex"
    elif os.getenv("OPENROUTER_API_KEY"):
        default_provider = "openrouter"
    elif os.getenv("KIE_API_KEY"):
        default_provider = "kie"

    config = {
        "provider": default_provider,
        "api_key": "",
        "model": PROVIDERS[default_provider]["default_model"]
    }

    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                config.update(saved)
        except Exception as e:
            logger.warning(f"Failed to read AI config file: {e}")

    # Fallback to env key if not stored in config
    active_prov = config.get("provider", "offline")
    if not config.get("api_key") and active_prov in PROVIDERS:
        env_var = PROVIDERS[active_prov].get("env_key")
        if env_var:
            config["api_key"] = os.getenv(env_var, "")

    return config

def save_ai_config(provider: str, api_key: Optional[str] = None, model: Optional[str] = None) -> Dict[str, Any]:
    """Save active provider and model to persistent JSON file."""
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider '{provider}'. Must be one of: {list(PROVIDERS.keys())}")

    current = load_ai_config()
    current["provider"] = provider
    
    if api_key is not None:
        current["api_key"] = api_key.strip()
    
    if model:
        current["model"] = model.strip()
    elif not current.get("model") or current.get("model") not in PROVIDERS[provider]["available_models"]:
        current["model"] = PROVIDERS[provider]["default_model"]

    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2)

    return current

def call_active_llm(prompt: str, system_prompt: Optional[str] = None) -> str:
    """
    Execute completion through the currently selected provider.
    Raises exception on network/quota failure so caller can fallback to offline templates.
    """
    config = load_ai_config()
    provider_name = config.get("provider", "offline")

    if provider_name == "offline":
        raise RuntimeError("AI provider set to 'offline'. Using template fallback.")

    meta = PROVIDERS.get(provider_name)
    if not meta:
        raise ValueError(f"Provider '{provider_name}' is not configured.")

    api_key = config.get("api_key")
    if not api_key:
        raise ValueError(f"API key for '{provider_name}' is missing. Please configure it in settings.")

    base_url = meta["base_url"].rstrip("/")
    url = f"{base_url}/chat/completions"
    model = config.get("model") or meta["default_model"]

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "AutomationTools-Agent/1.0"
    }
    if provider_name == "openrouter":
        headers["HTTP-Referer"] = "https://github.com/12345Shahid/Automation-Tools"
        headers["X-Title"] = "Outreach Automation Agent"

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 1200
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=45)
    if resp.status_code != 200:
        raise RuntimeError(f"{meta['name']} returned HTTP {resp.status_code}: {resp.text}")

    data = resp.json()
    choices = data.get("choices", [])
    if not choices or "message" not in choices[0]:
        raise RuntimeError(f"Unexpected response payload from {meta['name']}: {data}")

    return choices[0]["message"].get("content", "").strip()

def test_provider_connection(provider: str, api_key: str, model: Optional[str] = None) -> Dict[str, Any]:
    """Test connection and return latency / verification status."""
    if provider == "offline":
        return {"status": "ok", "provider": "offline", "message": "Offline dynamic fallback is active. Zero API tokens required."}

    meta = PROVIDERS.get(provider)
    if not meta:
        return {"status": "error", "message": f"Unknown provider: {provider}"}

    base_url = meta["base_url"].rstrip("/")
    url = f"{base_url}/chat/completions"
    test_model = model or meta["default_model"]

    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
        "User-Agent": "AutomationTools-Agent/1.0"
    }
    if provider == "openrouter":
        headers["HTTP-Referer"] = "https://github.com/12345Shahid/Automation-Tools"
        headers["X-Title"] = "Outreach Automation Agent"

    payload = {
        "model": test_model,
        "messages": [{"role": "user", "content": "Respond with 'CONNECTED' in one word."}],
        "max_tokens": 80
    }

    try:
        import time
        start_t = time.time()
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        elapsed = round((time.time() - start_t) * 1000, 1)

        if resp.status_code == 200:
            data = resp.json()
            reply = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {
                "status": "ok",
                "provider": provider,
                "model": test_model,
                "latency_ms": elapsed,
                "reply": reply.strip(),
                "message": f"Successfully connected to {meta['name']} ({elapsed}ms)!"
            }
        else:
            return {
                "status": "error",
                "provider": provider,
                "http_status": resp.status_code,
                "message": f"Connection failed (HTTP {resp.status_code}): {resp.text[:200]}"
            }
    except Exception as e:
        return {"status": "error", "provider": provider, "message": f"Network error connecting to {meta['name']}: {str(e)}"}
