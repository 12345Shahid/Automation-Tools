import re
import json
import requests
from typing import Dict, Any, List
from content_engine import config

STORY_SYSTEM_PROMPT = """You are a Master Viral Scriptwriter and Narrative Architect specializing in YouTube Shorts, TikTok, and Instagram Reels.
You write scripts using Jack Craig's Looped Arc Formula:
1. Phase 1: Open Loop Hook (0s - 7s): A riddle, shocking claim, or unanswered question that commands attention.
2. Phase 2: Rising Action (7s - 15s): The start of the journey or workflow.
3. Phase 3: The Conflict (15s - 25s): The obstacle, mistake, or price trap that stops 99% of people.
4. Phase 4: The Comeback (25s - 35s): The secret breakthrough or automated fix.
5. Phase 5: The Payoff (35s - 42s): The final loop close. The very last word must loop back seamlessly into the first sentence.

Word count target: 90 to 125 words total (40 to 45 seconds at natural spoken speed).
You must output pure JSON only, without markdown fences or outside commentary.
"""

def generate_looped_arc_story(topic: str, video_type: str = "option_a") -> Dict[str, Any]:
    """
    Story Architect Agent: generates the complete 5-phase Looped Arc script,
    scene visual descriptions, and metadata.
    """
    user_prompt = f"""Topic: {topic}
Type: {video_type} (option_a = automated stock/broll, option_b = screen proof roadmap)

Generate the complete Looped Arc script. Output JSON adhering to this exact schema:
{{
  "title": "Viral Clickable Title with 2 Emojis",
  "description": "2-sentence high-SEO description with keyword density",
  "hashtags": ["#shorts", "#ai", "#tech", "#viral"],
  "pinned_comment": "Call to action comment to drive comments and link clicks",
  "total_target_seconds": 42.0,
  "phases": [
    {{
      "phase_number": 1,
      "phase_name": "Open Loop Hook",
      "target_seconds": 7.0,
      "narration": "What if you could replace every paid monthly tool with completely free code?",
      "visual_query": "futuristic digital interface holographic neon",
      "on_screen_action": "Show impossible contrast hook"
    }},
    {{
      "phase_number": 2,
      "phase_name": "Rising Action",
      "target_seconds": 8.0,
      "narration": "Most people spend hundreds of dollars on subscriptions just to make simple edits.",
      "visual_query": "credit card payment decline software subscription",
      "on_screen_action": "Demonstrate the initial state"
    }},
    {{
      "phase_number": 3,
      "phase_name": "The Conflict",
      "target_seconds": 10.0,
      "narration": "Then your credits run out right in the middle of a major project, blocking your work.",
      "visual_query": "frustrated developer terminal error red screen",
      "on_screen_action": "Show the obstacle and error"
    }},
    {{
      "phase_number": 4,
      "phase_name": "The Comeback",
      "target_seconds": 10.0,
      "narration": "But when you switch to an open-weight model with a local runner, the entire job costs zero dollars.",
      "visual_query": "terminal code green matrix fast execution",
      "on_screen_action": "Execute the breakthrough fix"
    }},
    {{
      "phase_number": 5,
      "phase_name": "The Payoff",
      "target_seconds": 7.0,
      "narration": "And the crazy part is you never pay another subscription fee, which is...",
      "visual_query": "smiling person looking at laptop screen success",
      "on_screen_action": "Show finished payoff and loop back to start"
    }}
  ]
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
                    {"role": "system", "content": STORY_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 1500
            },
            timeout=25
        )
        if resp.status_code == 200:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                parsed = json.loads(match.group(0))
                # Add full joined narration
                parsed["full_narration"] = " ".join([p["narration"] for p in parsed.get("phases", [])])
                return parsed
    except Exception as e:
        print(f"[StoryArchitect] Warning: LLM call error ({e}). Using algorithmic Looped Arc story.")

    # High quality fallback
    phases = [
        {
            "phase_number": 1,
            "phase_name": "Open Loop Hook",
            "target_seconds": 7.0,
            "narration": f"What if you could replace a two hundred dollar monthly tool with free code running on your computer?",
            "visual_query": f"{topic} neon terminal code",
            "on_screen_action": "Show impossible contrast hook"
        },
        {
            "phase_number": 2,
            "phase_name": "Rising Action",
            "target_seconds": 8.0,
            "narration": "Most creators burn hours manually editing and paying subscription fees every single month.",
            "visual_query": "software credit card billing screen",
            "on_screen_action": "Demonstrate the initial state"
        },
        {
            "phase_number": 3,
            "phase_name": "The Conflict",
            "target_seconds": 10.0,
            "narration": "Then token limits and credit fees catch you off guard right when you need to ship.",
            "visual_query": "computer screen error dialog red warning",
            "on_screen_action": "Show the obstacle and error"
        },
        {
            "phase_number": 4,
            "phase_name": "The Comeback",
            "target_seconds": 10.0,
            "narration": "That is why smart operators are connecting open-source models to local skills for complete autonomy.",
            "visual_query": "fast green terminal execution code",
            "on_screen_action": "Execute the breakthrough fix"
        },
        {
            "phase_number": 5,
            "phase_name": "The Payoff",
            "target_seconds": 7.0,
            "narration": "Zero subscription, zero wait time, and complete ownership of your workflow, which is...",
            "visual_query": "successful person laptop high productivity",
            "on_screen_action": "Show finished payoff and loop back to start"
        }
    ]
    return {
        "title": f"The Secret {topic} Breakthrough in 2026 ⚡🤯",
        "description": f"How to master {topic} for $0 using autonomous AI workflows.",
        "hashtags": ["#shorts", "#ai", "#productivity", "#viral"],
        "pinned_comment": "Comment 'WORKFLOW' and I will send you the free template! 👇",
        "total_target_seconds": 42.0,
        "phases": phases,
        "full_narration": " ".join([p["narration"] for p in phases])
    }
