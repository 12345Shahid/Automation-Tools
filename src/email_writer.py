import json
import os
import random
import re
from typing import Dict, Optional, Any

from src.config import call_kie_deepseek

FALLBACK_TEMPLATES = {
    "default": [
        {
            "subject": "Quick question regarding {company_subject}",
            "body_intro": "I came across your profile and work at {company} and wanted to reach out directly.",
            "pitch": "I'm a full-stack web developer currently expanding my freelance client base. To collect initial reviews and client testimonials, I'm offering to design and build a modern, high-converting website for just $1 (essentially free in exchange for an honest review once you love the result).",
            "cta": "Would you be open to me putting together a quick draft or discussing this for 5 minutes this week?"
        },
        {
            "subject": "Can I build a custom website for {company_subject} ($1 review offer)?",
            "body_intro": "I hope you are having a productive week. I've been following {company} and love what you're doing.",
            "pitch": "I am currently offering to build 1 custom, mobile-optimized website for just $1. The reason for the $1 price is simple: I'm launching my freelance portfolio and prioritizing authentic testimonials and verified reviews over profit right now.",
            "cta": "If you could use a brand-new website or a sleek redesign, let me know if you'd be open to a quick chat."
        }
    ],
    "roofer_no_website": [
        {
            "subject": "I built a free website demo for {company_subject}",
            "body_intro": "I noticed {company} has a solid local reputation in Dallas, but I couldn't find an active website for your business.",
            "pitch": "I'm a web developer specializing in contractor websites. I actually went ahead and created a modern, mobile-friendly demo website for {company} completely for free so you can see how it looks and how many more homeowner calls it can generate.",
            "cta": "Would you be open to a quick 10-minute call this week so I can show it to you? Zero cost, no sales pitch or strings attached."
        },
        {
            "subject": "Quick website idea for {company_subject} (Free Demo)",
            "body_intro": "Hope your week is going well.",
            "pitch": "I noticed that when homeowners search for roofing services in Dallas, {company} pops up without a website link. I put together a quick, clean website concept for you completely for free to help you capture those customer leads.",
            "cta": "Could we hop on a 10-minute call this week so I can show you the demo? Let me know if you have a few minutes."
        }
    ],
    "it_contractor": [
        {
            "subject": "Independent contractor support for {company_subject}'s dev team",
            "body_intro": "Hope you're having a productive week.",
            "pitch": "I'm an independent full-stack software engineer reaching out to see if {company} ever needs reliable subcontracting support for client web and software projects. I deliver high-quality, production-grade code with fast turnaround at competitive contractor rates to help your core team handle overflow work smoothly.",
            "cta": "Would you be open to a brief 5-minute chat or connecting on LinkedIn to keep in touch for upcoming projects?"
        },
        {
            "subject": "Overflow developer capacity for {company_subject}",
            "body_intro": "I've been following {company}'s work and wanted to introduce myself directly.",
            "pitch": "I provide senior full-stack development as an independent contractor for digital and IT agencies. Whether you have overflow client deadlines or need an extra developer on short notice, I offer high-quality execution at flexible contractor rates.",
            "cta": "Would you be open to a quick 5-minute intro call or keeping my portfolio on file for your next project?"
        }
    ]
}

def infer_name_and_company(email: str, name: Optional[str] = None, company: Optional[str] = None) -> tuple[str, str]:
    """Infers name and company from an email address if not provided."""
    email_clean = email.strip()
    user_part, _, domain_part = email_clean.partition("@")
    
    if not name or name in ("there", "Owner", "Team"):
        cleaned_user = re.sub(r"[._\-\d+]+", " ", user_part).strip().title()
        if cleaned_user and len(cleaned_user) > 1 and not cleaned_user.lower() in ("info", "admin", "contact", "support", "hello", "sales", "team", "owner"):
            name = cleaned_user
        elif name:
            name = name
        else:
            name = "there"

    if not company:
        domain_name = domain_part.split(".")[0]
        if domain_name.lower() not in ("gmail", "yahoo", "hotmail", "outlook", "icloud", "proton", "aol"):
            company = domain_name.capitalize()
        else:
            company = "your business"

    return name, company

def generate_fallback_email(email: str, name: str, company: str, sender_name: str, campaign_type: str = "default") -> Dict[str, str]:
    """Generates a polished, professional email using curated templates when LLM is offline or quota exceeded."""
    templates = FALLBACK_TEMPLATES.get(campaign_type, FALLBACK_TEMPLATES["default"])
    template = random.choice(templates)
    
    company_subject = company if company != "your business" else "your business"
    name_subject = name if name != "there" else "your business"

    subject = template["subject"].format(company_subject=company_subject, name_subject=name_subject, company=company, name=name)
    intro = template["body_intro"].format(company=company, name=name)
    pitch = template["pitch"].format(company=company, name=name)
    cta = template["cta"].format(company=company, name=name)
    
    body_text = f"""Hi {name},

{intro}

{pitch}

{cta}

Best regards,
{sender_name}
Full-Stack Web Developer
"""

    body_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #222222; background-color: #ffffff; padding: 12px; }}
  p {{ margin-bottom: 16px; font-size: 15px; }}
  .footer {{ margin-top: 24px; padding-top: 16px; border-top: 1px solid #e5e7eb; color: #6b7280; font-size: 13px; }}
</style>
</head>
<body>
  <p>Hi {name},</p>
  <p>{intro}</p>
  <p>{pitch}</p>
  <p>{cta}</p>
  <div class="footer">
    <strong>{sender_name}</strong><br>
    <span>Full-Stack Web Developer</span>
  </div>
</body>
</html>"""

    return {
        "subject": subject,
        "body_text": body_text.strip(),
        "body_html": body_html.strip()
    }

def generate_outreach_email(
    email: str,
    name: Optional[str] = None,
    company: Optional[str] = None,
    custom_notes: Optional[str] = None,
    campaign_type: Optional[str] = None
) -> Dict[str, str]:
    """
    Generate an outreach email tailored to the lead and campaign type.
    Attempts to use DeepSeek LLM first; if quota/network error occurs, falls back gracefully.
    """
    sender_name = os.getenv("SENDER_NAME", "Shahid Hasan")
    resolved_name, resolved_company = infer_name_and_company(email, name, company)

    # Determine campaign type from explicit parameter or notes
    notes_lower = (custom_notes or "").lower()
    if not campaign_type:
        if any(w in notes_lower for w in ["roofer", "roofing", "no website", "demo website", "10 minute call", "10-minute"]):
            campaign_type = "roofer_no_website"
        elif any(w in notes_lower for w in ["contractor", "subcontract", "it agency", "software agency", "dev team"]):
            campaign_type = "it_contractor"
        else:
            campaign_type = "default"

    prompt = f"""
You are an expert cold email copywriter. Write a high-converting, friendly, ultra-concise outreach email from {sender_name} to {resolved_name} ({resolved_company}).

CAMPAIGN CONTEXT:
- Type: {campaign_type}
- Specific notes about lead: {custom_notes or 'None'}
- Goal: Short, personalized, polite, non-pushy, under 110 words.
- Sign-off: Best regards,\\n{sender_name}

Return ONLY a valid JSON object with exactly two keys:
{{
  "subject": "Catchy, personal, non-spam subject line (under 8 words)",
  "body": "Natural, friendly email text. Signed off with: Best regards,\\n{sender_name}"
}}
"""

    try:
        content = call_kie_deepseek(prompt)
        cleaned = content.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        
        parsed = json.loads(cleaned.strip())
        subject = parsed.get("subject", f"Quick question regarding {resolved_company}")
        body_text = parsed.get("body", "").strip()
        
        paragraphs = [p for p in body_text.split("\n\n") if p.strip()]
        html_paragraphs = "".join([f"<p>{p.replace(chr(10), '<br>')}</p>" for p in paragraphs])
        body_html = f"""<!DOCTYPE html>
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #222;">
{html_paragraphs}
</body>
</html>"""

        return {
            "subject": subject,
            "body_text": body_text,
            "body_html": body_html
        }
    except Exception:
        # Fallback to robust dynamic generator
        return generate_fallback_email(email, resolved_name, resolved_company, sender_name, campaign_type)
