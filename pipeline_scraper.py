#!/usr/bin/env python3
"""
Autonomous Lead Discovery & Google Maps Scraper (pipeline_scraper.py)
Uses Serper Google Places API to research businesses based on target audience & location,
cleans business metadata, normalizes phone numbers to E.164, and persists fresh leads to Supabase.
"""

import os
import re
import json
import logging
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

SERPER_API_KEY = os.environ.get("SERPER_API_KEY", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

def _get_supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

def normalize_phone_number(raw_phone: str, default_country: str = "US") -> Optional[str]:
    """Normalizes phone numbers to standard E.164 format."""
    if not raw_phone:
        return None
    # Strip spaces, hyphens, brackets
    digits = re.sub(r"[^\d+]", "", raw_phone)
    if not digits:
        return None

    if digits.startswith("+"):
        return digits
    elif len(digits) == 10 and default_country == "US":
        return f"+1{digits}"
    elif len(digits) == 11 and digits.startswith("1") and default_country == "US":
        return f"+{digits}"
    elif len(digits) == 11 and digits.startswith("0") and default_country == "BD":
        return f"+880{digits[1:]}"
    elif digits.startswith("880"):
        return f"+{digits}"
    elif digits.startswith("44") and default_country == "UK":
        return f"+{digits}"
    elif len(digits) >= 10:
        return f"+{digits}"
    return None

def clean_company_name(raw_name: str) -> str:
    """Removes marketing clutter and legal suffixes for natural conversational usage."""
    if not raw_name:
        return "Company"
    name = re.sub(r"\s*\(.*?\)", "", raw_name)
    name = re.sub(r",?\s*(LLC|Inc\.?|Corp\.?|Ltd\.?|Co\.?)\b", "", name, flags=re.I)
    name = re.sub(r"\s*-\s*(Best|Top|Premier|24/7|Roofing|Repairs).*", "", name, flags=re.I)
    name = name.strip()
    return name or raw_name.strip()

def is_phone_in_supabase(phone_number: str) -> bool:
    """Checks whether a lead with this phone number already exists in Supabase."""
    if not (SUPABASE_URL and SUPABASE_KEY):
        return False
    endpoint = f"{SUPABASE_URL}/rest/v1/calls_ai_leads?phone_number=eq.{requests.utils.quote(phone_number)}&select=id"
    try:
        res = requests.get(endpoint, headers=_get_supabase_headers(), timeout=8)
        if res.status_code == 200:
            return len(res.json()) > 0
    except Exception as e:
        logging.warning(f"Error checking duplicate in Supabase for {phone_number}: {e}")
    return False

def scrape_leads(
    industry: str = "Roofing contractors",
    location: str = "Dallas, TX",
    count: int = 10,
    tags: str = "google_maps_scrape"
) -> List[Dict[str, Any]]:
    """
    Scrapes business leads from Google Maps via Serper API and inserts fresh leads into Supabase.
    """
    if not SERPER_API_KEY:
        logging.error("❌ SERPER_API_KEY not configured in .env!")
        return []

    search_query = f"{industry} in {location}"
    logging.info(f"🔍 Searching Google Maps for: '{search_query}' (target: {count} leads)...")

    url = "https://google.serper.dev/places"
    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json"
    }
    
    gl_code = "us"
    if "bangladesh" in location.lower() or "dhaka" in location.lower():
        gl_code = "bd"
    elif "uk" in location.lower() or "london" in location.lower():
        gl_code = "gb"

    payload = {
        "q": search_query,
        "num": min(max(count * 2, 20), 100),
        "gl": gl_code,
        "hl": "en"
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        if response.status_code != 200:
            logging.error(f"❌ Serper API returned status {response.status_code}: {response.text}")
            return []
        
        data = response.json()
        places = data.get("places", [])
        logging.info(f"📍 Found {len(places)} raw business places from Google Maps.")
    except Exception as e:
        logging.error(f"❌ Serper request failed: {e}")
        return []

    fresh_leads = []
    skipped_duplicates = 0

    for p in places:
        if len(fresh_leads) >= count:
            break

        raw_phone = p.get("phoneNumber")
        if not raw_phone:
            continue

        normalized_phone = normalize_phone_number(raw_phone, default_country="US" if gl_code == "us" else "BD")
        if not normalized_phone:
            continue

        if is_phone_in_supabase(normalized_phone):
            skipped_duplicates += 1
            continue

        raw_title = p.get("title", "Business Lead")
        cleaned_company = clean_company_name(raw_title)
        website = p.get("website", "")
        address = p.get("address", location)
        rating = p.get("rating", 0)

        # Parse city and state from location or address
        loc_parts = [s.strip() for s in location.split(",")]
        city = loc_parts[0] if len(loc_parts) > 0 else "Dallas"
        state = loc_parts[1] if len(loc_parts) > 1 else "TX"

        lead_entry = {
            "company_name": cleaned_company,
            "phone_number": normalized_phone,
            "website": website,
            "city": city,
            "state": state,
            "group_name": "group3_unanswered",
            "outcome": "pending",
            "call_duration_seconds": 0,
            "transcript_summary": f"Scraped lead: {raw_title} | Rating: {rating} | Address: {address}",
            "tags": tags,
            "created_at": datetime.now().isoformat()
        }

        # Insert into Supabase
        if SUPABASE_URL and SUPABASE_KEY:
            try:
                ins_res = requests.post(
                    f"{SUPABASE_URL}/rest/v1/calls_ai_leads",
                    headers=_get_supabase_headers(),
                    json=lead_entry,
                    timeout=8
                )
                if ins_res.status_code in (200, 201):
                    logging.info(f"✅ Saved to Supabase: {cleaned_company} ({normalized_phone})")
                    fresh_leads.append(lead_entry)
                else:
                    logging.warning(f"⚠️ Supabase insert error {ins_res.status_code}: {ins_res.text}")
            except Exception as e:
                logging.error(f"❌ Failed to persist lead to Supabase: {e}")
        else:
            fresh_leads.append(lead_entry)

    logging.info(f"🎯 Scrape complete! Fresh leads queued: {len(fresh_leads)} | Skipped duplicates: {skipped_duplicates}")
    return fresh_leads

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Autonomous Google Maps Lead Discovery & Scraper")
    parser.add_argument("--industry", type=str, default="Roofing contractors", help="Target industry keyword")
    parser.add_argument("--location", type=str, default="Dallas, TX", help="Location (City, State/Country)")
    parser.add_argument("--count", type=int, default=10, help="Number of fresh leads to collect")
    parser.add_argument("--tags", type=str, default="google_maps_scrape", help="Campaign tags")
    args = parser.parse_args()

    leads = scrape_leads(industry=args.industry, location=args.location, count=args.count, tags=args.tags)
    print(f"\nDiscovered {len(leads)} fresh leads successfully queued into Supabase.")
