"""
Apollo & Multiformat Lead Parser Module
Ingests, normalizes, and extracts structured B2B lead records from Apollo CSV exports,
generic spreadsheets, and JSON files.
"""

import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger("apollo_parser")

# Header mapping variations from Apollo and CRM exports to standard fields
FIELD_MAPPINGS = {
    "first_name": [
        "first name", "firstname", "first", "fname", "given name"
    ],
    "last_name": [
        "last name", "lastname", "last", "lname", "surname", "family name"
    ],
    "full_name": [
        "name", "full name", "contact name", "lead name", "person name"
    ],
    "title": [
        "title", "job title", "role", "position", "occupation", "headline"
    ],
    "company": [
        "company", "company name", "organization", "company name for emails",
        "account name", "business name"
    ],
    "email": [
        "email", "email address", "work email", "corporate email", "contact email",
        "primary email", "verified email"
    ],
    "email_status": [
        "email status", "email confidence", "email validity", "status"
    ],
    "mobile_phone": [
        "mobile phone", "mobile", "cell phone", "cell", "personal phone"
    ],
    "corporate_phone": [
        "corporate phone", "work phone", "direct phone", "primary phone",
        "phone", "phone number", "company phone", "office phone", "telephone"
    ],
    "website": [
        "website", "company website", "domain", "url", "web"
    ],
    "linkedin": [
        "linkedin url", "person linkedin url", "linkedin", "profile url",
        "contact linkedin"
    ],
    "company_linkedin": [
        "company linkedin url", "company linkedin", "organization linkedin url"
    ],
    "industry": [
        "industry", "industry tag", "vertical", "sector", "category"
    ],
    "city": [
        "city", "person city", "company city", "metro"
    ],
    "state": [
        "state", "person state", "company state", "region", "province"
    ],
    "country": [
        "country", "person country", "company country", "nation"
    ],
    "revenue": [
        "annual revenue", "revenue", "estimated revenue"
    ],
    "employees": [
        "number of employees", "employees", "employee count", "headcount", "company size"
    ],
    "technologies": [
        "technologies", "tech stack", "technologies used"
    ],
    "keywords": [
        "keywords", "seo keywords", "tags", "specialties"
    ]
}


class ApolloLeadParser:
    """Parser for Apollo.io exports and generic B2B contact lists."""

    @staticmethod
    def _find_field(row: Dict[str, Any], field_key: str) -> str:
        """Finds matching field in row using fuzzy alias dictionary."""
        candidates = FIELD_MAPPINGS.get(field_key, [field_key])
        clean_keys = {k.strip().lower(): v for k, v in row.items() if k}

        for candidate in candidates:
            if candidate in clean_keys and clean_keys[candidate]:
                val = str(clean_keys[candidate]).strip()
                if val and val.lower() not in ("none", "null", "n/a", "undefined"):
                    return val
        return ""

    @classmethod
    def parse_file(cls, file_path: Union[str, Path]) -> List[Dict[str, Any]]:
        """Parses a CSV or JSON file and returns structured lead dictionaries."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Lead file does not exist: {path}")

        if path.suffix.lower() == ".json":
            return cls.parse_json(path)
        return cls.parse_csv(path)

    @classmethod
    def parse_csv(cls, file_path: Union[str, Path]) -> List[Dict[str, Any]]:
        """Parses CSV with header auto-detection and deduplication."""
        path = Path(file_path)
        leads = []
        seen_identifiers = set()

        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            reader = csv.DictReader(f)
            for row_idx, row in enumerate(reader):
                parsed = cls.normalize_row(row, row_idx=row_idx)
                
                # Check uniqueness by email, phone, or (name + company)
                identifier = parsed.get("email") or parsed.get("phone") or f"{parsed.get('full_name')}_{parsed.get('company')}"
                if not identifier or identifier in seen_identifiers:
                    continue
                seen_identifiers.add(identifier)
                leads.append(parsed)

        return leads

    @classmethod
    def parse_json(cls, file_path: Union[str, Path]) -> List[Dict[str, Any]]:
        """Parses JSON list of lead records."""
        path = Path(file_path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        raw_list = data if isinstance(data, list) else data.get("leads", data.get("contacts", []))
        leads = []
        seen_identifiers = set()

        for idx, item in enumerate(raw_list):
            if isinstance(item, dict):
                parsed = cls.normalize_row(item, row_idx=idx)
                identifier = parsed.get("email") or parsed.get("phone") or f"{parsed.get('full_name')}_{parsed.get('company')}"
                if not identifier or identifier in seen_identifiers:
                    continue
                seen_identifiers.add(identifier)
                leads.append(parsed)

        return leads

    @classmethod
    def normalize_row(cls, row: Dict[str, Any], row_idx: int = 0) -> Dict[str, Any]:
        """Maps an unformatted raw row into a clean, canonical lead record."""
        first_name = cls._find_field(row, "first_name")
        last_name = cls._find_field(row, "last_name")
        full_name = cls._find_field(row, "full_name")

        if not full_name and (first_name or last_name):
            full_name = f"{first_name} {last_name}".strip()
        elif full_name and not first_name:
            parts = full_name.split()
            first_name = parts[0] if parts else ""
            last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

        # Prioritize mobile phone for WhatsApp, fallback to corporate
        mobile_phone = cls._find_field(row, "mobile_phone")
        corp_phone = cls._find_field(row, "corporate_phone")
        primary_phone = mobile_phone or corp_phone

        # Location synthesis
        city = cls._find_field(row, "city")
        state = cls._find_field(row, "state")
        country = cls._find_field(row, "country") or "US"
        loc_parts = [p for p in [city, state, country] if p]
        location_str = ", ".join(loc_parts)

        # Website clean-up
        website = cls._find_field(row, "website")
        if website and not website.startswith("http"):
            website = f"https://{website}"

        lead = {
            "lead_id": f"lead_{row_idx + 1:04d}",
            "first_name": first_name or "there",
            "last_name": last_name,
            "full_name": full_name or "CEO / Business Leader",
            "title": cls._find_field(row, "title") or "CEO / Owner",
            "company": cls._find_field(row, "company") or "your company",
            "email": cls._find_field(row, "email"),
            "email_status": cls._find_field(row, "email_status"),
            "phone": primary_phone,
            "mobile_phone": mobile_phone,
            "corporate_phone": corp_phone,
            "website": website,
            "linkedin": cls._find_field(row, "linkedin"),
            "company_linkedin": cls._find_field(row, "company_linkedin"),
            "industry": cls._find_field(row, "industry"),
            "location": location_str,
            "country": country,
            "annual_revenue": cls._find_field(row, "revenue"),
            "employee_count": cls._find_field(row, "employees"),
            "technologies": cls._find_field(row, "technologies"),
            "keywords": cls._find_field(row, "keywords"),
            "raw_source": row
        }

        return lead
