"""
Company Digital Footprint & Ad Spend Leak Analyzer
Performs an automated audit of a target business:
- Detects active advertising tracking (Google Ads, Meta Pixel, TikTok, LinkedIn)
- Identifies revenue leaks (missing 24/7 speed-to-lead, no WhatsApp channel, traffic bouncing)
- Audits online reputation and reviews via Serper API
- Produces a crisp, personalized "Revenue Leak Diagnostic" to hook the CEO.
"""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional
import requests
from dotenv import load_dotenv
from src.apollo_scraper import ApolloApiClient

load_dotenv()
logger = logging.getLogger("audit_analyzer")


class CompanyAuditAnalyzer:
    """Analyzes digital footprint, ad spend, and conversion leaks for a target business."""

    def __init__(self, serper_api_key: Optional[str] = None):
        self.serper_api_key = serper_api_key or os.getenv("SERPER_API_KEY", "")
        self.serper_search_url = "https://google.serper.dev/search"
        self.serper_places_url = "https://google.serper.dev/places"
        self.headers = {
            "X-API-KEY": self.serper_api_key,
            "Content-Type": "application/json"
        }
        self.apollo_client = ApolloApiClient()

    def inspect_website_leaks(self, website_url: Optional[str]) -> Dict[str, Any]:
        """
        Crawls target website homepage to detect:
        1. Paid ad tracking pixels (Google Ads, Meta/Facebook, TikTok, LinkedIn)
        2. Conversion channels (WhatsApp button, live chat, lead forms)
        3. Revenue leak indicators (spending on ads without 24/7 lead capture)
        """
        default_result = {
            "website_checked": False,
            "accessible": False,
            "ads_running_detected": False,
            "ad_platforms": [],
            "has_whatsapp_widget": False,
            "has_live_chat": False,
            "has_phone_clickable": False,
            "revenue_leaks_identified": []
        }

        if not website_url or not isinstance(website_url, str):
            default_result["revenue_leaks_identified"].append("Missing or inactive public website")
            return default_result

        target_url = website_url if website_url.startswith("http") else f"https://{website_url}"
        default_result["website_checked"] = True

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
        }

        try:
            resp = requests.get(target_url, headers=headers, timeout=8, verify=False)
            if resp.status_code != 200:
                default_result["revenue_leaks_identified"].append(f"Website returned HTTP status {resp.status_code}")
                return default_result

            html = resp.text.lower()
            default_result["accessible"] = True

            # 1. Ad Pixel & Tracking Detection
            ad_platforms = []
            if any(sig in html for sig in ["gtag('config'", "googletagmanager.com/gtm.js", "google_conversion_id", "aw-"]):
                ad_platforms.append("Google Ads / Tag Manager")
            if any(sig in html for sig in ["connect.facebook.net", "fbq('init'", "facebook-pixel", "meta pixel"]):
                ad_platforms.append("Meta (Facebook/Instagram) Ads")
            if any(sig in html for sig in ["analytics.tiktok.com", "ttq.load"]):
                ad_platforms.append("TikTok Ads")
            if any(sig in html for sig in ["snap.licdn.com", "linkedin_data_partner_ids"]):
                ad_platforms.append("LinkedIn Insight Ads")

            default_result["ads_running_detected"] = len(ad_platforms) > 0
            default_result["ad_platforms"] = ad_platforms

            # 2. Conversion Channel Detection
            has_whatsapp = any(sig in html for sig in ["wa.me/", "api.whatsapp.com", "whatsapp.com/send", "whatsapp-widget"])
            has_chat = any(sig in html for sig in ["intercom", "crisp.chat", "drift.com", "zendesk", "tawk.to", "livechat", "tidio", "chat-widget"])
            has_phone_link = "tel:" in html

            default_result["has_whatsapp_widget"] = has_whatsapp
            default_result["has_live_chat"] = has_chat
            default_result["has_phone_clickable"] = has_phone_link

            # 3. Revenue Leak Synthesis
            leaks = []
            if default_result["ads_running_detected"]:
                if not has_whatsapp and not has_chat:
                    leaks.append(f"Spending budget on {', '.join(ad_platforms)} without 24/7 instant WhatsApp or Live Chat lead capture (traffic bounces after-hours)")
                elif not has_whatsapp:
                    leaks.append(f"Active {', '.join(ad_platforms)} traffic has no direct WhatsApp click-to-book path for mobile visitors")
            else:
                leaks.append("Relying primarily on organic search or word-of-mouth without an autonomous outbound lead engine")

            if not has_whatsapp:
                leaks.append("Zero instant WhatsApp booking channel on homepage")
            if not has_phone_link:
                leaks.append("No one-click call-to-dial button on mobile")

            default_result["revenue_leaks_identified"] = leaks
            return default_result

        except Exception as e:
            logger.debug(f"Website inspection error for {target_url}: {e}")
            default_result["revenue_leaks_identified"].append("Website slow to respond or blocked automated crawl")
            return default_result

    def query_serper_intelligence(self, company_name: str, location: str = "") -> Dict[str, Any]:
        """
        Uses Serper.dev API to retrieve company reputation, Google Places reviews,
        and recent online footprint.
        """
        if not self.serper_api_key:
            return {
                "serper_available": False,
                "rating": "N/A",
                "reviews_count": 0,
                "recent_snippet": "",
                "search_insights": []
            }

        search_query = f'"{company_name}" {location}'.strip()

        intel = {
            "serper_available": True,
            "rating": "N/A",
            "reviews_count": 0,
            "recent_snippet": "",
            "search_insights": []
        }

        # 1. Search Google Places for reviews and sentiment
        try:
            p_resp = requests.post(
                self.serper_places_url,
                headers=self.headers,
                json={"q": search_query, "num": 5},
                timeout=10
            )
            if p_resp.status_code == 200:
                places = p_resp.json().get("places", [])
                if places:
                    p = places[0]
                    intel["rating"] = str(p.get("rating", "N/A"))
                    intel["reviews_count"] = p.get("ratingCount", 0)
        except Exception:
            pass

        # 2. Search News & Web Footprint
        try:
            s_resp = requests.post(
                self.serper_search_url,
                headers=self.headers,
                json={"q": f'"{company_name}" news OR announcement OR reviews', "num": 4},
                timeout=10
            )
            if s_resp.status_code == 200:
                organic = s_resp.json().get("organic", [])
                snippets = []
                for res in organic[:3]:
                    snip = res.get("snippet", "").strip()
                    if snip and len(snip) > 20:
                        snippets.append(snip)
                if snippets:
                    intel["recent_snippet"] = snippets[0]
                    intel["search_insights"] = snippets
        except Exception:
            pass

        return intel

    def conduct_full_audit(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """
        Runs comprehensive audit combining website leak analysis and Serper search intel.
        Returns a concise diagnostic with the primary revenue leak and the unified fix.
        """
        company = lead.get("company", "Your Company")
        website = lead.get("website", "")
        location = lead.get("location", "")

        site_audit = self.inspect_website_leaks(website)
        search_audit = self.query_serper_intelligence(company, location)

        # Enrich organization details via Apollo if domain exists
        apollo_org_info = {}
        if website and self.apollo_client.is_configured():
            apollo_org_info = self.apollo_client.enrich_organization(website) or {}

        # Merge Apollo technologies into ad platforms if detected
        apollo_techs = apollo_org_info.get("technologies", [])
        for tech in apollo_techs:
            t_low = tech.lower()
            if any(ad_sig in t_low for ad_sig in ["google ads", "facebook pixel", "meta pixel", "tiktok", "linkedin insight", "retargeting"]):
                if tech not in site_audit["ad_platforms"]:
                    site_audit["ad_platforms"].append(tech)
                    site_audit["ads_running_detected"] = True

        # Determine Primary Revenue Leak
        primary_leak = "Dormant past customer leads sitting in CRM/inbox without automated reactivation"
        if site_audit["ads_running_detected"] and not site_audit["has_whatsapp_widget"]:
            primary_leak = f"Running {', '.join(site_audit['ad_platforms'])} traffic without 24/7 instant WhatsApp lead capture — losing after-hours leads"
        elif not site_audit["accessible"] and website:
            primary_leak = "Company website has slow response or downtime, causing paid/organic visitor drop-off"
        elif search_audit["reviews_count"] and search_audit["reviews_count"] < 15:
            primary_leak = "Low volume of recent customer reviews, leaving local authority on the table"

        # The Unified 4-in-1 Solution Formulation
        solution_pitch = (
            f"1) An automated Lead Reactivation sequence to revive past 2024-2025 inquiries at $0 ad cost; "
            f"2) A 24/7 AI Speed-to-Lead WhatsApp & Voice Agent to immediately capture and book every inbound visitor; "
            f"3) Full visibility analytics pinpointing where marketing spend is leaking."
        )

        return {
            "company": company,
            "website_audit": site_audit,
            "search_audit": search_audit,
            "primary_revenue_leak": primary_leak,
            "solution_pitch": solution_pitch,
            "has_ad_spend": site_audit["ads_running_detected"],
            "ad_platforms": site_audit["ad_platforms"],
            "rating": search_audit["rating"],
            "reviews_count": search_audit["reviews_count"],
            "apollo_enrichment": apollo_org_info,
            "top_insight": search_audit["recent_snippet"] or f"{company}'s online presence in {location or 'their market'}"
        }
