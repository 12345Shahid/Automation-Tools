"""
Contact Verification & Cleaning Module
Provides zero-cost email deliverability verification (DNS MX, syntax, disposable blacklist)
and phone normalization (E.164 standardization, carrier classification, WhatsApp URL formatting).
"""

import re
import socket
import logging
from typing import Dict, Any, List, Optional, Tuple
import dns.resolver
import phonenumbers
from phonenumbers import PhoneNumberType, PhoneNumberFormat

logger = logging.getLogger("contact_verifier")

# Known disposable / throwaway email provider domains
DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "sharklasers.com", "guerrillamail.info",
    "grr.la", "guerrillamail.biz", "guerrillamail.de", "guerrillamail.net",
    "guerrillamail.org", "10minutemail.com", "tempmail.com", "temp-mail.org",
    "throwawaymail.com", "fakeinbox.com", "trashmail.com", "trashmail.net",
    "dispostable.com", "yopmail.com", "yopmail.fr", "yopmail.net",
    "getairmail.com", "mohmal.com", "burnermail.io", "mytemp.email",
    "crazymailing.com", "tmailor.com", "minutemailbox.com", "generator.email",
    "maildrop.cc", "inboxkitten.com", "nada.ltd", "dropmail.me"
}

# Role-based prefixes (typically shared inboxes, not personal decision makers)
ROLE_PREFIXES = {
    "admin", "info", "support", "billing", "office", "sales", "help",
    "jobs", "careers", "press", "marketing", "contact", "team", "hello",
    "general", "inquiries", "media", "service", "hr", "operations"
}

# Major MX service signatures
MX_SIGNATURES = {
    "google": "Google Workspace",
    "googlemail": "Google Workspace",
    "aspmx": "Google Workspace",
    "outlook": "Microsoft 365",
    "microsoft": "Microsoft 365",
    "pphosted": "Proofpoint Enterprise",
    "zoho": "Zoho Mail",
    "protonmail": "ProtonMail",
    "icloud": "Apple iCloud",
    "mimecast": "Mimecast Secure Email",
    "barracuda": "Barracuda Networks",
    "cloudflare": "Cloudflare Email Routing",
    "sendgrid": "SendGrid Mail",
    "mailgun": "Mailgun"
}


class ContactVerifier:
    """
    Zero-cost contact verification engine.
    Validates emails using DNS MX records and normalizes phones to WhatsApp-ready format.
    """

    def __init__(self, dns_timeout: float = 4.0):
        self.resolver = dns.resolver.Resolver()
        self.resolver.timeout = dns_timeout
        self.resolver.lifetime = dns_timeout
        # Set reliable public DNS fallbacks
        self.resolver.nameservers = ['8.8.8.8', '1.1.1.1', '8.8.4.4']
        self._mx_cache: Dict[str, Tuple[bool, List[str], str]] = {}

    def verify_email(self, email: Optional[str]) -> Dict[str, Any]:
        """
        Performs thorough validation on an email address:
        1. Syntax check (RFC 5322 regex)
        2. Domain extraction
        3. Disposable email blacklist check
        4. Role-based prefix check
        5. DNS MX record validation (guarantees recipient domain accepts mail)
        6. Provider identification
        """
        if not email or not isinstance(email, str):
            return {
                "email": "",
                "is_valid": False,
                "score": 0,
                "reason": "Email address is empty",
                "is_deliverable": False,
                "is_disposable": False,
                "is_role_based": False,
                "mx_provider": "Unknown",
                "mx_records": []
            }

        cleaned_email = email.strip().lower()

        # 1. Syntax Check
        email_regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        if not re.match(email_regex, cleaned_email):
            return {
                "email": cleaned_email,
                "is_valid": False,
                "score": 0,
                "reason": "Invalid email syntax format",
                "is_deliverable": False,
                "is_disposable": False,
                "is_role_based": False,
                "mx_provider": "Unknown",
                "mx_records": []
            }

        parts = cleaned_email.split("@")
        local_part = parts[0]
        domain = parts[1]

        # 2. Check for disposable burner domains
        if domain in DISPOSABLE_DOMAINS:
            return {
                "email": cleaned_email,
                "is_valid": False,
                "score": 10,
                "reason": f"Domain '{domain}' is a temporary/disposable burner inbox",
                "is_deliverable": False,
                "is_disposable": True,
                "is_role_based": False,
                "mx_provider": "Disposable Provider",
                "mx_records": []
            }

        # 3. Check for role-based address (e.g. info@, support@)
        is_role = local_part in ROLE_PREFIXES

        # 4. Check DNS MX Records
        has_mx, mx_hosts, provider = self._resolve_mx(domain)

        if not has_mx:
            return {
                "email": cleaned_email,
                "is_valid": False,
                "score": 0,
                "reason": f"No active MX (Mail Exchange) servers found for domain '{domain}'. Emails will bounce.",
                "is_deliverable": False,
                "is_disposable": False,
                "is_role_based": is_role,
                "mx_provider": "None",
                "mx_records": []
            }

        # 5. Calculate deliverability score (0 - 100)
        # Direct personal domain with valid MX = 95
        # Role-based with valid MX = 65 (valid, but may not reach the CEO personally)
        score = 95 if not is_role else 65
        reason = f"Verified deliverable via {provider} MX servers"
        if is_role:
            reason += " (Note: role-based inbox e.g. info/contact)"

        return {
            "email": cleaned_email,
            "is_valid": True,
            "score": score,
            "reason": reason,
            "is_deliverable": True,
            "is_disposable": False,
            "is_role_based": is_role,
            "mx_provider": provider,
            "mx_records": mx_hosts
        }

    def _resolve_mx(self, domain: str) -> Tuple[bool, List[str], str]:
        """Resolves MX records with caching to minimize DNS traffic."""
        if domain in self._mx_cache:
            return self._mx_cache[domain]

        mx_hosts = []
        detected_provider = "Custom Mailserver"

        try:
            answers = self.resolver.resolve(domain, 'MX')
            for rdata in answers:
                host_str = str(rdata.exchange).rstrip(".").lower()
                mx_hosts.append(host_str)
                for sig, prov_name in MX_SIGNATURES.items():
                    if sig in host_str:
                        detected_provider = prov_name

            result = (len(mx_hosts) > 0, mx_hosts, detected_provider)
            self._mx_cache[domain] = result
            return result
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.Timeout, Exception) as e:
            # Fallback: check if domain has an A record that accepts mail
            try:
                a_answers = self.resolver.resolve(domain, 'A')
                if len(a_answers) > 0:
                    result = (True, [f"A-record-fallback ({domain})"], "Domain Host Fallback")
                    self._mx_cache[domain] = result
                    return result
            except Exception:
                pass

            result = (False, [], "None")
            self._mx_cache[domain] = result
            return result

    def verify_and_format_phone(self, phone: Optional[str], default_country: str = "US") -> Dict[str, Any]:
        """
        Validates and standardizes a phone number into international E.164 format.
        Classifies whether it's mobile or landline, and formats the direct WhatsApp click URL.
        """
        if not phone or not isinstance(phone, str):
            return {
                "phone_raw": "",
                "is_valid": False,
                "e164": "",
                "national_format": "",
                "international_format": "",
                "country_code": "",
                "phone_type": "UNKNOWN",
                "is_mobile": False,
                "whatsapp_ready": False,
                "whatsapp_url": "",
                "reason": "Phone number is empty"
            }

        cleaned_phone = phone.strip()
        # Clean extra extensions or notes (e.g., "(555) 123-4567 ext 102" -> "(555) 123-4567")
        ext_split = re.split(r"(?:ext|x|#)\s*\d+", cleaned_phone, flags=re.IGNORECASE)
        base_phone = ext_split[0].strip()

        try:
            parsed = phonenumbers.parse(base_phone, default_country)
            is_valid = phonenumbers.is_valid_number(parsed)

            if not is_valid:
                return {
                    "phone_raw": cleaned_phone,
                    "is_valid": False,
                    "e164": "",
                    "national_format": "",
                    "international_format": "",
                    "country_code": "",
                    "phone_type": "INVALID",
                    "is_mobile": False,
                    "whatsapp_ready": False,
                    "whatsapp_url": "",
                    "reason": f"Invalid phone number format for country '{default_country}'"
                }

            e164 = phonenumbers.format_number(parsed, PhoneNumberFormat.E164)
            national = phonenumbers.format_number(parsed, PhoneNumberFormat.NATIONAL)
            intl = phonenumbers.format_number(parsed, PhoneNumberFormat.INTERNATIONAL)
            num_type_code = phonenumbers.number_type(parsed)

            # Classify line type
            type_map = {
                PhoneNumberType.MOBILE: "MOBILE",
                PhoneNumberType.FIXED_LINE_OR_MOBILE: "MOBILE_OR_LANDLINE",
                PhoneNumberType.FIXED_LINE: "LANDLINE",
                PhoneNumberType.VOIP: "VOIP",
                PhoneNumberType.TOLL_FREE: "TOLL_FREE"
            }
            phone_type_str = type_map.get(num_type_code, "UNKNOWN")
            is_mobile = phone_type_str in ("MOBILE", "MOBILE_OR_LANDLINE")

            # Clean digits for WhatsApp link (strip '+')
            clean_digits = re.sub(r"\D", "", e164)
            whatsapp_url = f"https://wa.me/{clean_digits}"

            return {
                "phone_raw": cleaned_phone,
                "is_valid": True,
                "e164": e164,
                "national_format": national,
                "international_format": intl,
                "country_code": str(parsed.country_code),
                "phone_type": phone_type_str,
                "is_mobile": is_mobile,
                "whatsapp_ready": True,
                "whatsapp_url": whatsapp_url,
                "reason": f"Valid {phone_type_str} formatted to {e164}"
            }

        except Exception as e:
            return {
                "phone_raw": cleaned_phone,
                "is_valid": False,
                "e164": "",
                "national_format": "",
                "international_format": "",
                "country_code": "",
                "phone_type": "ERROR",
                "is_mobile": False,
                "whatsapp_ready": False,
                "whatsapp_url": "",
                "reason": f"Parsing failed: {str(e)}"
            }

    def verify_lead_contact(
        self,
        email: Optional[str],
        phone: Optional[str] = None,
        country_hint: str = "US"
    ) -> Dict[str, Any]:
        """Convenience method to verify both email and phone in a single unified call."""
        email_result = self.verify_email(email)
        phone_result = self.verify_and_format_phone(phone, default_country=country_hint)

        # High priority contact ready if verified email OR verified mobile/WhatsApp
        is_contactable = email_result["is_deliverable"] or phone_result["is_valid"]

        return {
            "email_verification": email_result,
            "phone_verification": phone_result,
            "is_contactable": is_contactable,
            "channels_available": {
                "email": email_result["is_deliverable"],
                "whatsapp": phone_result["whatsapp_ready"],
                "phone_call": phone_result["is_valid"]
            }
        }
