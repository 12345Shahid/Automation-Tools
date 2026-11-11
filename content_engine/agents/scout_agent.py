import re
import json
import requests
from typing import Dict, Any, List
from content_engine import config

SCOUT_SYSTEM_PROMPT = """You are a World-Class Viral Content Researcher & Trend Scout for YouTube Shorts, TikTok, and Instagram Reels.
Your objective is to identify viral outliers, high-contrast hooks, and low-competition narrative angles based on Jack Craig's viral criteria:
1. High Viewership Potential: Strong emotional contrast (e.g. Free vs $200, Simple vs Impossible).
2. Curiosity Gap: Poses an open loop that viewers cannot abandon without watching to the end.
3. Low Competition: Explores unique angles rather than repeating generic slogans.

You must output valid, pure JSON without any surrounding conversational text or markdown code fences.
"""

def scout_viral_angle(seed_topic: str) -> Dict[str, Any]:
    """
    Research agent: generates 3 high-impact viral video angles, hooks, and search queries for a seed topic.
    """
    prompt = f"""Seed Topic: {seed_topic}

Generate 3 viral video concepts. Output pure JSON adhering to this schema:
{{
  "seed_topic": "{seed_topic}",
  "angles": [
    {{
      "title": "Short punchy video title with 2 emojis",
      "hook_sentence": "Opening 3-second hook creating an open loop",
      "core_conflict": "The unexpected obstacle or shocking fact",
      "visual_search_terms": ["term 1", "term 2", "term 3"]
    }}
  ],
  "recommended_angle_index": 0
}}
"""
    headers = {
        "Authorization": f"Bearer {config.MOONMATH_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }

    try:
        resp = requests.post(
            f"{config.MOONMATH_BASE_URL}/chat/completions",
            headers=headers,
            json={
                "model": "glm-5.3-flash",
                "messages": [
                    {"role": "system", "content": SCOUT_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 1200
            },
            timeout=25
        )
        if resp.status_code == 200:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                return json.loads(match.group(0))
    except Exception as e:
        print(f"[ScoutAgent] Warning: LLM call error ({e}). Using algorithmic viral scout.")

    # Robust algorithmic fallback
    return {
        "seed_topic": seed_topic,
        "angles": [
            {
                "title": f"Why Everyone Is Wrong About {seed_topic} 🤯🔥",
                "hook_sentence": f"What if the way you were told to handle {seed_topic} was completely backwards?",
                "core_conflict": "Most people spend hours and hundreds of dollars doing this manually.",
                "visual_search_terms": [f"{seed_topic} screen", "computer code matrix", "frustrated person typing"]
            },
            {
                "title": f"This $0 Tool Replaced a $200 Subscription ⚡",
                "hook_sentence": "This free terminal code literally just saved me two hundred dollars this month.",
                "core_conflict": "SaaS companies hide this because it kills their business model.",
                "visual_search_terms": ["digital credit card decline", "terminal command execute", "celebration success"]
            }
        ],
        "recommended_angle_index": 0
    }
