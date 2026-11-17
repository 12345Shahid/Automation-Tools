"""
Unified All-in-One Pitch Generator Module
Combines the 4-Pillar Package into a cohesive, irresistible value-first outreach:
1. Analytics & Ad Spend Leak Audit (identifies where the CEO is losing money)
2. Dormant Lead Reactivation Engine (performance-based cash injection from old leads)
3. 24/7 AI Speed-to-Lead & WhatsApp Voice Agent (captures after-hours inbound demand)
4. Outbound Appointment Pipeline

Generates:
- Personalized Cold Email (engineered for high open & reply rates)
- WhatsApp Conversational Message
- Live Voice Call Script & Context for live_voice_agent.py
"""

import json
import logging
import os
import re
from typing import Any, Dict, Optional
from src.ai_provider import call_active_llm

logger = logging.getLogger("pitch_generator")


class UnifiedPitchGenerator:
    """Generates multi-channel personalized outreach pitches for CEOs and business leaders."""

    def __init__(self):
        pass

    def generate_all_pitches(
        self,
        lead: Dict[str, Any],
        audit_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Synthesizes the complete multi-channel pitch package for a lead.
        Attempts LLM generation first; falls back to dynamic high-converting templates if offline.
        """
        first_name = lead.get("first_name") or "there"
        if first_name.lower() in ("team", "owner", "there", "ceo"):
            first_name = "there"

        company = lead.get("company") or "your company"
        primary_leak = audit_data.get("primary_revenue_leak", "Dormant past customer leads sitting idle in CRM")
        ad_spend = audit_data.get("has_ad_spend", False)
        ad_platforms = ", ".join(audit_data.get("ad_platforms", []))
        location = lead.get("location") or "your market"

        # Attempt LLM generation
        llm_pitches = self._generate_with_llm(lead, audit_data)
        if llm_pitches:
            return llm_pitches

        # Fallback to high-converting structured template
        return self._generate_fallback_pitches(lead, audit_data)

    def _generate_with_llm(self, lead: Dict[str, Any], audit_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Uses active AI Provider (MoonMath, APInex, OpenRouter) to write custom hyper-personalized copy."""
        first_name = lead.get("first_name", "there")
        company = lead.get("company", "your company")
        title = lead.get("title", "CEO")
        leak = audit_data.get("primary_revenue_leak", "")
        ad_platforms = audit_data.get("ad_platforms", [])
        has_ads = audit_data.get("has_ad_spend", False)
        insight = audit_data.get("top_insight", "")

        system_prompt = (
            "You are an elite B2B revenue consultant writing cold outreach to a CEO/business leader.\n"
            "We are offering a unified 4-pillar package:\n"
            "1. Digital Ad & Revenue Leak Audit (analyzing where ad spend or website visitors bounce)\n"
            "2. Dormant Lead Reactivation (reviving past 2024-2025 dead leads on 100% performance split)\n"
            "3. 24/7 AI Speed-to-Lead & WhatsApp Voice Agent (capturing after-hours inquiries in 5 seconds)\n"
            "RULES:\n"
            "- Tone: Sharp, conversational, respectful, zero fluff or buzzwords.\n"
            "- Cold Email: Max 4 sentences. Subject line in lowercase or natural text. Low friction CTA.\n"
            "- WhatsApp Message: 2 sentences max. Friendly and direct.\n"
            "- Voice Script: Spoken by 'Sarah' on live WhatsApp phone call. 1-2 spoken sentences only.\n"
            "Output strictly valid JSON with keys: email_subject, email_body, whatsapp_text, voice_opening_script."
        )

        user_content = (
            f"Recipient: {first_name} ({title} at {company})\n"
            f"Ad spend running: {'Yes (' + ', '.join(ad_platforms) + ')' if has_ads else 'No direct ad pixels detected'}\n"
            f"Identified Revenue Leak: {leak}\n"
            f"Recent Search Insight: {insight}\n"
            "Draft the outreach in valid JSON."
        )

        try:
            resp = call_active_llm(
                prompt=user_content,
                system_prompt=system_prompt,
                temperature=0.7,
                max_tokens=600
            )

            # Extract JSON block
            json_match = re.search(r"\{.*\}", resp, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(0))
                if all(k in parsed for k in ["email_subject", "email_body", "whatsapp_text", "voice_opening_script"]):
                    return {
                        "email_subject": parsed["email_subject"],
                        "email_body": parsed["email_body"],
                        "whatsapp_text": parsed["whatsapp_text"],
                        "voice_opening_script": parsed["voice_opening_script"],
                        "generation_method": "ai_llm"
                    }
        except Exception as e:
            logger.debug(f"LLM pitch generation fallback triggered: {e}")

        return None

    def _generate_fallback_pitches(self, lead: Dict[str, Any], audit_data: Dict[str, Any]) -> Dict[str, Any]:
        """Deterministic high-converting pitch templates incorporating real audit data."""
        first_name = lead.get("first_name", "there")
        company = lead.get("company", "your company")
        primary_leak = audit_data.get("primary_revenue_leak", "dormant leads sitting in CRM")
        has_ads = audit_data.get("has_ad_spend", False)
        ad_platforms = ", ".join(audit_data.get("ad_platforms", []))

        # 1. Cold Email
        if has_ads:
            email_subject = f"quick question on {company}'s ad spend & after-hours leads"
            email_body = (
                f"Hi {first_name},\n\n"
                f"I took a look at {company}'s digital setup and noticed you're investing in {ad_platforms} traffic, "
                f"but prospective leads reaching out after hours have no instant 24/7 WhatsApp or speed-to-lead response—meaning ad dollars are leaking on bounced visitors.\n\n"
                f"We install a complete Revenue Optimization package for companies like yours: 1) A 24/7 AI WhatsApp & Voice Agent that qualifies and books leads in 5 seconds, "
                f"and 2) A zero-risk Lead Reactivation engine that revives your past 2024–2025 dead leads on a pure performance split (you only pay if we put cash in your bank).\n\n"
                f"Would you be open to a 2-minute diagnostic video showing where the traffic leaks are and how we fix them?"
            )
        else:
            email_subject = f"revenue leak audit & dormant leads for {company}"
            email_body = (
                f"Hi {first_name},\n\n"
                f"I was researching {company} and put together a quick digital revenue leak audit for your team.\n\n"
                f"Most businesses in your space sit on 200–500 unclosed past leads from 2024–2025 that their sales reps gave up on. "
                f"We set up a unified AI revenue engine that 1) revives your dormant lead database on a 100% performance commission (zero upfront cost), "
                f"and 2) connects a 24/7 AI WhatsApp Speed-to-Lead assistant so new inquiries never get lost.\n\n"
                f"Would you be open to seeing the 1-page leak breakdown to see if this could unlock an extra $5k–$15k in recovered revenue this month?"
            )

        # 2. WhatsApp Conversational Message
        if has_ads:
            wa_text = (
                f"Hey {first_name}, saw {company}'s active campaigns on {ad_platforms}. "
                f"Ran a quick audit and spotted where after-hours mobile visitors are dropping off before booking. "
                f"We set up 24/7 WhatsApp AI booking and performance lead reactivation—mind if I share the 1-page breakdown with you here?"
            )
        else:
            wa_text = (
                f"Hey {first_name}, noticed {company}'s work and put together a quick revenue leak audit. "
                f"We're helping companies revive their dead 2024–2025 leads over WhatsApp on a pure performance split (zero upfront cost). "
                f"Open to seeing the 1-page overview?"
            )

        # 3. Live Voice Script for live_voice_agent.py
        voice_script = (
            f"Hi {first_name}, this is Sarah calling briefly from Digital Growth Partners. "
            f"I'm reaching out because we ran a quick revenue audit on {company} and noticed a massive opportunity to revive your past unclosed customer leads on a pure performance split. "
            f"Do you have two minutes, or would you prefer I send the 1-page breakdown over WhatsApp?"
        )

        return {
            "email_subject": email_subject,
            "email_body": email_body,
            "whatsapp_text": wa_text,
            "voice_opening_script": voice_script,
            "generation_method": "performance_template"
        }
