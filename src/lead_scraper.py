import csv
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

class LeadScraper:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("SERPER_API_KEY", "")
        if not self.api_key:
            raise ValueError("SERPER_API_KEY is not defined. Please check your .env file.")
        self.places_url = "https://google.serper.dev/places"
        self.search_url = "https://google.serper.dev/search"
        self.headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }

    def _enrich_email_and_contacts(self, company_name: str, location: str, phone: Optional[str] = None) -> Optional[str]:
        """Search Google via Serper to find public email addresses for a local business."""
        query = f'"{company_name}" {location} email OR "@gmail.com" OR "@yahoo.com"'
        try:
            resp = requests.post(
                self.search_url,
                headers=self.headers,
                json={"q": query, "num": 5, "gl": "us", "hl": "en"},
                timeout=12
            )
            if resp.status_code != 200:
                return None

            text = resp.text
            # Regex for standard emails
            raw_emails = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)
            
            # Filter out search engine and system false positives
            blacklisted_domains = ["google", "serper", "sentry", "example", "schema.org", "wix", ".png", ".jpg", "github"]
            valid_emails = [
                e.strip().rstrip(".").lower() 
                for e in raw_emails 
                if not any(bad in e.lower() for bad in blacklisted_domains) and len(e.split("@")[0]) > 2
            ]

            return valid_emails[0] if valid_emails else None
        except Exception:
            return None

    def _crawl_website_for_email(self, website_url: str) -> Optional[str]:
        """Attempt to extract email from a company's website homepage or contact page."""
        if not website_url:
            return None
        
        target_url = website_url if website_url.startswith("http") else f"https://{website_url}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        }

        pages_to_check = [target_url]
        base_clean = target_url.rstrip("/")
        pages_to_check.extend([f"{base_clean}/contact", f"{base_clean}/contact-us", f"{base_clean}/about"])

        blacklisted = ["sentry", "example", "schema", "wix", ".png", ".jpg", "cloudflare", "bootstrap"]

        for page in pages_to_check:
            try:
                r = requests.get(page, headers=headers, timeout=6)
                if r.status_code == 200:
                    emails = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", r.text)
                    valid = [e.strip().rstrip(".").lower() for e in emails if not any(b in e.lower() for b in blacklisted)]
                    if valid:
                        # Prioritize contact@, info@, hello@
                        for v in valid:
                            if any(prefix in v for prefix in ["contact", "info", "hello", "sales", "support"]):
                                return v
                        return valid[0]
            except Exception:
                continue

        return None

    def find_local_businesses(
        self,
        industry: str = "roofing contractors",
        location: str = "Dallas, TX",
        count: int = 10,
        no_website_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Find local businesses in target location.
        Filters specifically for businesses without websites if `no_website_only` is True.
        """
        # Expand queries across neighborhood zones if needed to reach target count
        sub_locations = [
            f"{industry} {location}",
            f"{industry} South {location}",
            f"{industry} Oak Cliff {location}",
            f"{industry} Pleasant Grove {location}",
            f"{industry} Garland TX",
            f"{industry} Irving TX",
            f"{industry} Carrollton TX",
            f"independent {industry} {location}"
        ]

        leads = []
        seen_names = set()

        for q in sub_locations:
            if len(leads) >= count:
                break

            try:
                resp = requests.post(
                    self.places_url,
                    headers=self.headers,
                    json={"q": q, "location": location, "gl": "us", "hl": "en", "num": 20},
                    timeout=15
                )
                if resp.status_code != 200:
                    continue

                places = resp.json().get("places", [])
                for p in places:
                    title = p.get("title", "").strip()
                    if not title or title.lower() in seen_names:
                        continue

                    has_website = bool(p.get("website"))
                    if no_website_only and has_website:
                        continue

                    seen_names.add(title.lower())

                    # Enrich email
                    found_email = self._enrich_email_and_contacts(title, location, p.get("phoneNumber"))

                    lead_item = {
                        "company": title,
                        "name": title.split()[0] if title else "Owner",
                        "phone": p.get("phoneNumber", "N/A"),
                        "address": p.get("address", "N/A"),
                        "website": p.get("website", ""),
                        "has_website": has_website,
                        "rating": p.get("rating", "N/A"),
                        "rating_count": p.get("ratingCount", 0),
                        "email": found_email or "",
                        "category": p.get("category", industry),
                        "target_type": "local_business_no_website" if not has_website else "local_business"
                    }
                    leads.append(lead_item)

                    if len(leads) >= count:
                        break
            except Exception:
                continue

        return leads

    def find_it_companies(
        self,
        query: str = "IT consulting software development agency",
        location: str = "Dallas, TX",
        count: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Find IT companies and contracting agencies, extracting contact emails from their web presence.
        """
        leads = []
        seen = set()

        try:
            resp = requests.post(
                self.places_url,
                headers=self.headers,
                json={"q": f"{query} {location}", "gl": "us", "hl": "en", "num": 20},
                timeout=15
            )
            if resp.status_code == 200:
                places = resp.json().get("places", [])
                for p in places:
                    title = p.get("title", "").strip()
                    if not title or title.lower() in seen:
                        continue
                    seen.add(title.lower())

                    website = p.get("website", "")
                    found_email = self._crawl_website_for_email(website) if website else None
                    if not found_email:
                        found_email = self._enrich_email_and_contacts(title, location, p.get("phoneNumber"))

                    leads.append({
                        "company": title,
                        "name": "Team",
                        "phone": p.get("phoneNumber", "N/A"),
                        "address": p.get("address", "N/A"),
                        "website": website,
                        "has_website": bool(website),
                        "rating": p.get("rating", "N/A"),
                        "rating_count": p.get("ratingCount", 0),
                        "email": found_email or "",
                        "category": "IT / Software Agency",
                        "target_type": "it_agency_contractor"
                    })

                    if len(leads) >= count:
                        break
        except Exception:
            pass

        return leads

    def export_to_csv(self, leads: List[Dict[str, Any]], filename: str = "scraped_leads.csv") -> Path:
        """Export leads list to CSV file compatible with email agent."""
        p = Path(filename)
        if p.is_absolute():
            out_path = p
        elif p.parts and p.parts[0] == "data":
            out_path = BASE_DIR / p
        else:
            out_path = DATA_DIR / p

        out_path.parent.mkdir(parents=True, exist_ok=True)

        headers = ["email", "name", "company", "phone", "address", "website", "has_website", "rating", "target_type"]
        
        with open(out_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
            writer.writeheader()
            for lead in leads:
                writer.writerow(lead)

        return out_path
