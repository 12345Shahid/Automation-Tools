"""
Apollo Lead Scraper & API Extractor Module (src/apollo_scraper.py)
Provides dual-mode lead sourcing from Apollo.io:
1. Apollo Direct API Mode: Searches and extracts CEO / founder emails and phones using an Apollo API Key.
2. Apollo Chrome Browser Scraper Mode: Extracts prospects directly from active Apollo.io web sessions via Chrome Debugging (port 9222).
"""

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("apollo_scraper")

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class ApolloApiClient:
    """Interacts with Apollo.io official REST API to search and enrich CEO/founder leads."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("APOLLO_API_KEY", "")
        self.search_url = "https://api.apollo.io/v1/mixed_people/search"
        self.match_url = "https://api.apollo.io/v1/people/match"
        self.headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Api-Key": self.api_key
        }

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def search_leads(
        self,
        titles: Optional[List[str]] = None,
        keywords: Optional[str] = None,
        location: Optional[str] = "United States",
        count: int = 10,
        page: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Searches Apollo's prospect database for decision makers matching criteria.
        """
        if not self.api_key:
            raise ValueError(
                "APOLLO_API_KEY is not configured in your .env file. "
                "Add APOLLO_API_KEY=your_key or use the browser scraper mode."
            )

        target_titles = titles or ["CEO", "Founder", "Owner", "Chief Executive Officer", "President"]

        payload = {
            "api_key": self.api_key,
            "page": page,
            "per_page": min(count, 100),
            "person_titles": target_titles
        }

        if keywords:
            payload["q_keywords"] = keywords

        if location:
            payload["person_locations"] = [location]

        try:
            resp = requests.post(self.search_url, json=payload, headers=self.headers, timeout=15)
            if resp.status_code == 403 and "Free plan" in resp.text:
                logger.warning(
                    "Apollo Free Plan restriction: Apollo blocks direct REST API people search on Free accounts. "
                    "Use CSV export or the Chrome browser scraper mode (--scrape-apollo-browser)."
                )
                print(
                    "\n[Apollo Notice] Apollo.io blocks direct People Search via API on Free plans (HTTP 403).\n"
                    "-> To extract leads for FREE from Apollo without upgrading to paid ($49/mo):\n"
                    "   1. Export a CSV from app.apollo.io and run: uv run python ceo_outreach_agent.py --input <your_file.csv>\n"
                    "   2. OR open app.apollo.io in Chrome and run: uv run python ceo_outreach_agent.py --scrape-apollo-browser\n"
                )
                return []
            elif resp.status_code != 200:
                logger.error(f"Apollo API error: {resp.status_code} - {resp.text}")
                return []

            data = resp.json()
            people = data.get("people", [])
            extracted_leads = []

            for p in people:
                lead = self._normalize_apollo_person(p)
                extracted_leads.append(lead)

            return extracted_leads
        except Exception as e:
            logger.error(f"Failed to query Apollo API: {e}")
            return []

    def enrich_organization(self, domain: str) -> Optional[Dict[str, Any]]:
        """
        Enriches organization details (tech stack, size, phone, address) via Apollo API.
        This endpoint is supported on Apollo Free plans.
        """
        if not self.api_key or not domain:
            return None

        clean_domain = domain.replace("https://", "").replace("http://", "").split("/")[0]
        try:
            resp = requests.post(
                "https://api.apollo.io/v1/organizations/enrich",
                json={"api_key": self.api_key, "domain": clean_domain},
                headers=self.headers,
                timeout=12
            )
            if resp.status_code == 200:
                org = resp.json().get("organization", {})
                return {
                    "name": org.get("name"),
                    "website": org.get("website_url"),
                    "employees": org.get("estimated_num_employees"),
                    "phone": org.get("phone"),
                    "technologies": org.get("technology_names", []),
                    "industry": org.get("industry"),
                    "city": org.get("city"),
                    "state": org.get("state"),
                    "raw": org
                }
        except Exception as e:
            logger.debug(f"Apollo org enrichment failed: {e}")
        return None

    def enrich_person(
        self,
        first_name: str,
        last_name: str,
        domain: str,
        reveal_phone: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Reveals verified email and mobile phone number using Apollo match endpoint."""
        if not self.api_key:
            return None

        payload = {
            "api_key": self.api_key,
            "first_name": first_name,
            "last_name": last_name,
            "domain": domain,
            "reveal_personal_emails": True,
            "reveal_phone_number": reveal_phone
        }

        try:
            resp = requests.post(self.match_url, json=payload, headers=self.headers, timeout=15)
            if resp.status_code == 200:
                person = resp.json().get("person", {})
                return self._normalize_apollo_person(person)
        except Exception as e:
            logger.debug(f"Apollo match failed: {e}")
        return None

    def _normalize_apollo_person(self, p: Dict[str, Any]) -> Dict[str, Any]:
        """Maps an Apollo raw person record into our canonical lead schema."""
        org = p.get("organization") or {}
        phone_numbers = p.get("phone_numbers") or []
        primary_phone = ""
        mobile_phone = ""

        for ph in phone_numbers:
            raw_num = ph.get("raw_number", "")
            ph_type = ph.get("type", "").lower()
            if "mobile" in ph_type and not mobile_phone:
                mobile_phone = raw_num
            elif not primary_phone:
                primary_phone = raw_num

        return {
            "first_name": p.get("first_name", ""),
            "last_name": p.get("last_name", ""),
            "full_name": p.get("name") or f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
            "title": p.get("title", "CEO"),
            "company": org.get("name") or p.get("organization_name", "Company"),
            "email": p.get("email", ""),
            "email_status": p.get("email_status", ""),
            "phone": mobile_phone or primary_phone,
            "mobile_phone": mobile_phone,
            "corporate_phone": primary_phone,
            "website": org.get("website_url") or org.get("primary_domain", ""),
            "linkedin": p.get("linkedin_url", ""),
            "location": f"{p.get('city', '')}, {p.get('state', '')}, {p.get('country', 'US')}".strip(", "),
            "country": p.get("country", "US"),
            "raw_source": p
        }


class ApolloChromeBrowserScraper:
    """
    Scrapes contacts from an active Apollo.io web app session in Google Chrome.
    Connects via Chrome Remote Debugging port 9222 (configured in .env).
    """

    def __init__(self, debug_port: int = 9222):
        self.debug_port = debug_port
        self.cdp_url = f"http://127.0.0.1:{debug_port}"

    def is_chrome_ready(self) -> bool:
        """Checks if Chrome is running with remote debugging enabled."""
        import urllib.request
        try:
            with urllib.request.urlopen(f"{self.cdp_url}/json/version", timeout=1.5) as r:
                return r.status == 200
        except Exception:
            return False

    def scrape_active_apollo_tab(self) -> List[Dict[str, Any]]:
        """
        Extracts visible prospect rows from an open Apollo.io search tab in Chrome.
        Uses CDP JavaScript evaluation without triggering bot bans.
        """
        if not self.is_chrome_ready():
            raise RuntimeError(
                f"Chrome is not running on port {self.debug_port}. "
                "Launch Chrome with: python cli.py launch-chrome"
            )

        import requests
        try:
            # Get list of open Chrome tabs
            tabs_resp = requests.get(f"{self.cdp_url}/json", timeout=3)
            tabs = tabs_resp.json()
            apollo_tab = None

            for t in tabs:
                url = t.get("url", "")
                if "apollo.io" in url and t.get("type") == "page":
                    apollo_tab = t
                    break

            if not apollo_tab:
                raise RuntimeError("No active 'apollo.io' tab found in open Chrome browser.")

            tab_id = apollo_tab.get("id")
            # Connect via websocket and evaluate extraction JS
            import websocket
            ws_url = apollo_tab.get("webSocketDebuggerUrl")
            ws = websocket.create_connection(ws_url, timeout=10)

            # JavaScript snippet to extract prospect table rows from Apollo DOM
            js_extractor = """
            (() => {
                const results = [];
                // Query table rows on Apollo prospects search page
                const rows = document.querySelectorAll('tr[data-cy="table-row"], div.zp_table-row, div[role="row"]');
                rows.forEach(r => {
                    const nameEl = r.querySelector('a[data-cy="table-cell-name"], a.zp_name, .zp_t7h3Z');
                    const titleEl = r.querySelector('.zp_job-title, [data-cy="title-cell"], .zp_hnd6o');
                    const companyEl = r.querySelector('.zp_company-name, [data-cy="company-cell"], a[href*="/companies/"]');
                    const emailEl = r.querySelector('a[href^="mailto:"], [data-cy*="email"]');
                    const phoneEl = r.querySelector('a[href^="tel:"], [data-cy*="phone"]');
                    
                    const name = nameEl ? nameEl.innerText.trim() : '';
                    const title = titleEl ? titleEl.innerText.trim() : '';
                    const company = companyEl ? companyEl.innerText.trim() : '';
                    const email = emailEl ? emailEl.innerText.trim() : '';
                    const phone = phoneEl ? phoneEl.innerText.trim() : '';
                    
                    if (name || company) {
                        results.push({ name, title, company, email, phone });
                    }
                });
                return results;
            })()
            """

            req_payload = {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": js_extractor,
                    "returnByValue": True
                }
            }
            ws.send(json.dumps(req_payload))
            raw_eval = ws.recv()
            ws.close()

            eval_res = json.loads(raw_eval)
            rows = eval_res.get("result", {}).get("result", {}).get("value", [])

            leads = []
            for item in rows:
                parts = item.get("name", "").split()
                first = parts[0] if parts else "there"
                last = " ".join(parts[1:]) if len(parts) > 1 else ""
                leads.append({
                    "first_name": first,
                    "last_name": last,
                    "full_name": item.get("name") or "CEO / Owner",
                    "title": item.get("title") or "CEO",
                    "company": item.get("company") or "Company",
                    "email": item.get("email", ""),
                    "phone": item.get("phone", ""),
                    "website": "",
                    "location": "US",
                    "country": "US"
                })

            return leads

        except Exception as e:
            logger.error(f"Error scraping Apollo Chrome tab: {e}")
            raise
