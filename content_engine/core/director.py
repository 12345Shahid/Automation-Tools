import re
import json
import requests
from content_engine import config

DIRECTOR_SYSTEM_PROMPT = """You are an elite YouTube Shorts Director and Viral Strategist.
The creator wants to create a high-converting, high-retention Short based on an existing viral topic, video transcript, or tool.
You must give the creator a step-by-step 'Recording Roadmap' (what to show on screen for 45s) AND the final polished studio script.

The creator will casually talk while recording their screen as a guide. The AI engine will then wipe out their voice and replace it with a studio narrator.

Strict Rules:
1. Looped-Arc Framework (5 Steps):
   - Step 1: Open Loop Question Hook (0-7s)
   - Step 2: Rising Action / Standard Way (7-15s)
   - Step 3: Conflict / The Twist / Problem (15-25s)
   - Step 4: Comeback / The Breakthrough (25-35s)
   - Step 5: Payoff / Climax & Conclusion (35-45s)
2. Exact Screen Instructions: Tell the creator exactly what website to open, what button to click, or what terminal command to type.
3. Casual Guide Phrases: Tell the creator what simple words to say while recording so the AI can sync the scenes.
4. Polished Studio Script: Total spoken words must be 75 to 110 words (~35-45s).

Output ONLY valid JSON matching this schema:
{
  "viral_hook_concept": "Why Everyone Is Wrong About...",
  "target_duration": "40-45 seconds",
  "recording_instructions": "Record your screen (phone or computer). Don't worry about being perfect. Speak loosely while clicking so the engine can track your actions.",
  "shot_list": [
    {
      "step": 1,
      "stage": "Hook",
      "time_window": "0s - 7s",
      "action_on_screen": "Open the expensive software pricing page showing $200/mo.",
      "what_to_say_guide": "Look at this pricing page, two hundred dollars a month."
    },
    {
      "step": 2,
      "stage": "Rising Action",
      "time_window": "7s - 15s",
      "action_on_screen": "Open your terminal or browser and navigate to the free tool.",
      "what_to_say_guide": "Now open the free alternative tool."
    },
    {
      "step": 3,
      "stage": "Conflict",
      "time_window": "15s - 25s",
      "action_on_screen": "Show the error or limitation in the paid tool.",
      "what_to_say_guide": "Notice how the paid tool throttles you."
    },
    {
      "step": 4,
      "stage": "Comeback",
      "time_window": "25s - 35s",
      "action_on_screen": "Execute the automated command and watch it run.",
      "what_to_say_guide": "The free script finishes in forty seconds."
    },
    {
      "step": 5,
      "stage": "Payoff",
      "time_window": "35s - 45s",
      "action_on_screen": "Show the final working result and output.",
      "what_to_say_guide": "Here is the final result with zero cost."
    }
  ],
  "polished_script": {
    "title": "He replaced a $200 tool with free terminal code 😲😲",
    "description": "Here is how autonomous AI tools allow you to do high-end work for $0.",
    "hashtags": ["#shorts", "#ai", "#tech", "#viral"],
    "pinned_comment": "Grab the free template in my bio 👇 Comment 'TOOL' for the link!",
    "narration": "What if you could replace a two hundred dollar monthly tool with free code running right on your laptop? Most people burn hours manually editing and paying recurring fees. But when you connect an open-weight model to local scripts, the entire pipeline executes in forty seconds. Zero subscription, zero wasted time, and the exact same result."
  }
}
"""

def generate_director_roadmap(source_input: str) -> dict:
    """Generate the Director's Recording Roadmap + Polished Studio Script using GLM 5.3 Flash."""
    user_prompt = f"Source Content / Topic:\n{source_input}\n\nAnalyze this and generate the full Director Recording Roadmap and Polished Script. Output JSON only."
    
    # Try GLM 5.3 Flash on MoonMath
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
                    "model": "glm-5.3-flash",
                    "messages": [
                        {"role": "system", "content": DIRECTOR_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 1600
                },
                timeout=30
            )
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                json_match = re.search(r"\{.*\}", content, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(0))
        except Exception as e:
            print(f"[Director] GLM 5.3 Flash error: {e}")

    # Fallback to DeepSeek V4.1
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
                    "model": "deepseek-v4.1-flash",
                    "messages": [
                        {"role": "system", "content": DIRECTOR_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 1600
                },
                timeout=25
            )
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                json_match = re.search(r"\{.*\}", content, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(0))
        except Exception as e:
            print(f"[Director] DeepSeek fallback error: {e}")

    # Built-in robust template fallback
    print("[Director] Using built-in Director Roadmap template")
    cleaned = source_input[:60].strip()
    return {
        "viral_hook_concept": f"Why Everyone Is Wrong About {cleaned}",
        "target_duration": "40-45 seconds",
        "recording_instructions": "Record your screen for ~45 seconds. Follow the 5 steps below. Speak casually as you click so the AI editor tracks your actions. Your voice will be stripped and replaced with studio narration.",
        "shot_list": [
            {
                "step": 1,
                "stage": "Hook",
                "time_window": "0s - 7s",
                "action_on_screen": f"Show the standard problem or pricing related to {cleaned}.",
                "what_to_say_guide": "Look at how people usually struggle with this."
            },
            {
                "step": 2,
                "stage": "Rising Action",
                "time_window": "7s - 15s",
                "action_on_screen": "Switch to your workflow, tool, or browser tab.",
                "what_to_say_guide": "Now let's switch to the secret automated setup."
            },
            {
                "step": 3,
                "stage": "Conflict",
                "time_window": "15s - 25s",
                "action_on_screen": "Demonstrate the obstacle or error that usually stops beginners.",
                "what_to_say_guide": "Most people get stuck right here."
            },
            {
                "step": 4,
                "stage": "Comeback",
                "time_window": "25s - 35s",
                "action_on_screen": "Execute the fix, trigger the script, or run the AI workflow.",
                "what_to_say_guide": "Here is how you bypass it in ten seconds."
            },
            {
                "step": 5,
                "stage": "Payoff",
                "time_window": "35s - 45s",
                "action_on_screen": "Show the final output, result, or completed asset.",
                "what_to_say_guide": "And just like that, the entire workflow is done."
            }
        ],
        "polished_script": {
            "title": f"Why Everyone Is Wrong About {cleaned} 😲😲",
            "description": f"Step-by-step breakdown of how to automate {cleaned} for $0.",
            "hashtags": ["#shorts", "#ai", "#automation", "#viral"],
            "pinned_comment": "Comment 'WORKFLOW' to get the full script 👇",
            "narration": f"What if the way you were told to handle {cleaned} was completely backwards? Most people spend hours doing this by hand. But when you switch to an autonomous pipeline, the computer handles the entire execution in seconds. Zero wasted effort, and massive results on day one."
        }
    }
