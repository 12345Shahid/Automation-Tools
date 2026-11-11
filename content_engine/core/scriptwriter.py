import os
import json
import re
import requests
from content_engine import config

SYSTEM_PROMPT = """You are an elite YouTube Shorts strategist trained on the viral 'Looped Arc' and 'Open Loop' methodologies.
Your task is to take a topic and write a high-retention, high-converting 35-50 second YouTube Short script.

Strict Rules:
1. UNIVERSAL RELATABILITY: Make the concept easy to understand for any human in 2 seconds. No unnecessary jargon.
2. THE LOOPED ARC (5 Stages):
   - Stage 1 (Hook): Must be an OPEN LOOP QUESTION. Never make a closed statement. Plant curiosity that forces them to stay.
   - Stage 2 (Rising Action): The setup or standard way people do things.
   - Stage 3 (Conflict): The twist, major mistake, hidden cost, or shocking problem.
   - Stage 4 (Comeback): The breakthrough discovery or simple fix.
   - Stage 5 (Payoff): The shocking final result, conclusion, and payoff.
3. PACING: Total narration must be 70 to 110 words across all 5 scenes (approx 35-45 seconds spoken).
4. METADATA:
   - Title: Short, punchy, curiosity-driven + 2 shock emojis (e.g. He built an AI video engine for $0 😲😲)
   - Description: 2-3 sentences explaining the takeaway.
   - Hashtags: 4 hashtags (always include #shorts #viral + 2 niche tags).
   - Pinned Comment: A compelling Call-To-Action (e.g. "Grab the full free automation blueprint in my bio 👇").

Return ONLY valid JSON matching this schema:
{
  "title": "He ran an entire YouTube channel with free AI 😲😲",
  "description": "Here is how autonomous AI agents can create, edit, and post videos with $0 budget.",
  "hashtags": ["#shorts", "#ai", "#automation", "#viral"],
  "pinned_comment": "Grab the free template and script in my bio 👇 Comment 'TOOL' for the link!",
  "scenes": [
    {
      "id": 1,
      "stage": "Hook",
      "narration": "What would happen if you let an autonomous AI run your entire YouTube channel for $0?",
      "visual_prompt": "cinematic futuristic cyberpunk workstation glowing screens holographic AI assistant dark neon room 8k",
      "on_screen_keyword": "FOR $0?"
    },
    {
      "id": 2,
      "stage": "Rising Action",
      "narration": "Most creators spend 6 hours every day filming, cutting footage, and burning money on expensive tools.",
      "visual_prompt": "stressed content creator surrounded by glowing computer monitors in dark room video timeline",
      "on_screen_keyword": "SPEND 6 HOURS"
    },
    {
      "id": 3,
      "stage": "Conflict",
      "narration": "Until they realize that 90 percent of those viral faceless clips are actually built with code.",
      "visual_prompt": "matrix code cascading on screen digital glitch red warning light technology shock",
      "on_screen_keyword": "BUILT WITH CODE"
    },
    {
      "id": 4,
      "stage": "Comeback",
      "narration": "By combining free open models with terminal agents, the entire video renders in 40 seconds.",
      "visual_prompt": "ultra fast high tech data processing glowing golden fibers quantum computer hyper realistic",
      "on_screen_keyword": "40 SECONDS"
    },
    {
      "id": 5,
      "stage": "Payoff",
      "narration": "Zero filming, zero voice recording, and 100 percent original content that passes monetization.",
      "visual_prompt": "golden trophy glowing on modern tech desk luxury minimalist celebration 3d render",
      "on_screen_keyword": "100% ORIGINAL"
    }
  ]
}
"""

def generate_script(topic: str = "How to automate video creation with free AI") -> dict:
    """Generate a viral Looped-Arc script from a topic using LLM or smart fallback."""
    user_prompt = f"Topic: {topic}\nWrite a viral 5-scene Looped Arc YouTube Short script following the system rules. Output only the JSON object."
    
    # Try MoonMath Zro first
    if config.MOONMATH_API_KEY:
        try:
            resp = requests.post(
                f"{config.MOONMATH_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {config.MOONMATH_API_KEY}",
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0"
                },
                json={
                    "model": config.MOONMATH_MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 1200
                },
                timeout=25
            )
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                # Parse JSON
                json_match = re.search(r"\{.*\}", content, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(0))
        except Exception as e:
            print(f"[ScriptWriter] MoonMath request error: {e}")

    # Fallback to Kie if configured
    if config.KIE_API_KEY:
        try:
            resp = requests.post(
                f"{config.KIE_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {config.KIE_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": config.KIE_MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 1200
                },
                timeout=20
            )
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                json_match = re.search(r"\{.*\}", content, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(0))
        except Exception as e:
            print(f"[ScriptWriter] Kie request error: {e}")

    # High-converting smart fallback template
    print("[ScriptWriter] Using built-in Looped-Arc algorithmic template")
    cleaned_topic = topic.strip().capitalize()
    return {
        "title": f"Why Everyone Is Wrong About {cleaned_topic} 😲😲",
        "description": f"Here is the secret breakdown of {cleaned_topic} using automated AI tools.",
        "hashtags": ["#shorts", "#ai", "#tech", "#viral"],
        "pinned_comment": "Comment 'SYSTEM' to get the full free template 👇",
        "scenes": [
            {
                "id": 1,
                "stage": "Hook",
                "narration": f"What if everything you were told about {topic} was completely backwards?",
                "visual_prompt": "futuristic neon terminal displaying glowing questions and tech mysteries in dark room 8k",
                "on_screen_keyword": "COMPLETELY BACKWARDS?"
            },
            {
                "id": 2,
                "stage": "Rising Action",
                "narration": "Most people spend months trying to figure this out manually, burning hours with zero results.",
                "visual_prompt": "exhausted person in dark office glowing computer screens late night coffee tech",
                "on_screen_keyword": "ZERO RESULTS"
            },
            {
                "id": 3,
                "stage": "Conflict",
                "narration": "Until they hit a wall and realize the entire system was designed to keep them stuck.",
                "visual_prompt": "digital brick wall glitching red security warning neon cybernetic obstruction",
                "on_screen_keyword": "HIT A WALL"
            },
            {
                "id": 4,
                "stage": "Comeback",
                "narration": "That is when smart builders switch to automated workflows that execute the entire process in seconds.",
                "visual_prompt": "high speed fiber optic neon light pulses flowing through modern microchip technology",
                "on_screen_keyword": "IN SECONDS"
            },
            {
                "id": 5,
                "stage": "Payoff",
                "narration": "The exact same output, zero wasted effort, and massive results on day one.",
                "visual_prompt": "celebration glowing cyber trophy minimalist luxury tech office victory",
                "on_screen_keyword": "DAY ONE"
            }
        ]
    }
