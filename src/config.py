import json
import os
import requests
from pathlib import Path
from typing import Any, Dict, Optional
from dotenv import load_dotenv

# Load .env file
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

def get_candidate_profile(profile_path: Optional[str] = None) -> Dict[str, Any]:
    """Load candidate profile from JSON file."""
    path = Path(profile_path) if profile_path else Path(os.getenv("CANDIDATE_PROFILE_PATH", DATA_DIR / "candidate_profile.json"))
    if not path.is_absolute():
        path = BASE_DIR / path
    
    if not path.exists():
        raise FileNotFoundError(f"Candidate profile not found at {path}. Please create it or copy candidate_profile.json.")
    
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def call_kie_deepseek(prompt: str) -> str:
    """
    Call Kie.ai DeepSeek model via the OpenAI Responses endpoint.
    """
    kie_key = os.getenv("KIE_API_KEY")
    if not kie_key:
        raise ValueError("KIE_API_KEY is not defined in your environment or .env file.")

    model_name = os.getenv("KIE_MODEL", "deepseek-v4-1-flash")
    url = "https://api.kie.ai/openai/v1/responses"
    headers = {
        "Authorization": f"Bearer {kie_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model_name,
        "input": prompt,
        "stream": False
    }

    response = requests.post(url, headers=headers, json=payload, timeout=45)
    if response.status_code != 200:
        raise RuntimeError(f"Kie API returned status {response.status_code}: {response.text}")

    data = response.json()
    for item in data.get("output", []):
        if item.get("type") == "message" and item.get("content"):
            for part in item["content"]:
                if part.get("text"):
                    return part["text"]

    raise RuntimeError(f"No text content found in Kie DeepSeek response: {data}")

def get_llm():
    """
    Instantiate the appropriate LLM based on environment variables.
    Supports Kie.ai, OpenAI, Anthropic Claude, and Google Gemini.
    """
    kie_key = os.getenv("KIE_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")
    custom_model = os.getenv("LLM_MODEL")

    # If Kie.ai key is set, use OpenAI-compatible client
    if kie_key:
        from langchain_openai import ChatOpenAI
        base_url = os.getenv("KIE_BASE_URL", "https://api.kie.ai/openai/v1")
        model_name = custom_model or os.getenv("KIE_MODEL", "deepseek-v4-1-flash")
        return ChatOpenAI(
            model=model_name,
            api_key=kie_key,
            base_url=base_url
        )

    if anthropic_key:
        from langchain_anthropic import ChatAnthropic
        model_name = custom_model or "claude-3-5-sonnet-20241022"
        return ChatAnthropic(model_name=model_name, api_key=anthropic_key)

    if gemini_key:
        from langchain_google_genai import ChatGoogleGenerativeAI
        model_name = custom_model or "gemini-2.0-flash"
        return ChatGoogleGenerativeAI(model=model_name, google_api_key=gemini_key)

    if openai_key:
        from langchain_openai import ChatOpenAI
        model_name = custom_model or "gpt-4o"
        return ChatOpenAI(model=model_name, api_key=openai_key)

    raise ValueError(
        "No LLM API key detected. Please define KIE_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY, or GEMINI_API_KEY in your .env file."
    )
