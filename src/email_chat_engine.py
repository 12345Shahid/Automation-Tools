import os
import re
from typing import Any, Dict, List, Optional

from src.email_reader import EmailReader
from src.email_sender import EmailSender
from src.email_writer import generate_outreach_email, infer_name_and_company
from src.lead_scraper import LeadScraper

class EmailChatEngine:
    def __init__(self):
        self.sender = EmailSender()
        self.reader = EmailReader()

    def process_chat(self, user_message: str, history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """
        Process a conversational user message, detect intent, execute actions,
        and return a formatted response with structured payload.
        """
        msg = user_message.strip()
        msg_lower = msg.lower()

        # 1. SCRAPE LEADS & AUTONOMOUS DISCOVERY INTENT
        # e.g. "find 10 roofers from Dallas who don't have a website and fill up their contact details into CSV"
        # or "find 10 IT companies in Dallas for contracting"
        scrape_triggers = ["roofer", "roofing", "contractor", "companies", "without a website", "don't have a website", "no website", "scrape", "collect", "fill up", "it companies", "into a csv", "into csv"]
        is_scrape_intent = any(trigger in msg_lower for trigger in ["scrape", "collect", "who don't have a website", "without a website", "fill up their contact", "into a csv"]) or \
                           (any(t in msg_lower for t in ["find", "get"]) and any(ind in msg_lower for ind in ["roofer", "roofing", "it companies", "contractors", "agencies"]))

        if is_scrape_intent:
            return self._handle_scrape_leads_intent(msg)

        # 2. SEND EMAIL INTENT
        # e.g. "email alex@acme.com and tell him I can build a website for $1"
        # or "send an email to test@domain.com saying..."
        email_pattern = r"[\w\.-]+@[\w\.-]+\.\w+"
        emails_found = re.findall(email_pattern, msg)

        send_triggers = ["email ", "send email", "mail ", "send a mail", "write to ", "message ", "reach out to "]
        is_send_intent = any(trigger in msg_lower for trigger in send_triggers) or (emails_found and any(w in msg_lower for w in ["send", "write", "offer", "tell", "say", "email"]))

        if is_send_intent and emails_found:
            recipient_email = emails_found[0]
            return self._handle_send_email_intent(msg, recipient_email)

        # 3. CHECK INBOX INTENT
        # e.g. "check my emails", "check my last 5 emails", "what are my latest emails", "recent emails", "check inbox"
        check_inbox_pattern = r"(check|show|read|fetch|get|view|list|what are|see)\s+(?:my\s+)?(?:recent\s+|latest\s+|last\s+\d*\s*)?(?:emails?|inbox|messages?)"
        is_inbox_intent = bool(re.search(check_inbox_pattern, msg_lower)) or bool(re.search(r"\b(inbox|recent emails?|latest emails?|unread emails?)\b", msg_lower))

        if is_inbox_intent and not any(w in msg_lower for w in ["find", "search", "about", "from "]):
            return self._handle_check_inbox_intent(msg)

        # 4. SEARCH / FIND EMAILS INTENT
        # e.g. "find emails from google", "find emails from test@example.com", "search emails about invoice"
        search_triggers = ["find email", "search email", "look for email", "find any email", "emails from", "email from", "search for", "find "]
        if any(trigger in msg_lower for trigger in search_triggers) or ("search" in msg_lower) or ("from " in msg_lower and "email" in msg_lower):
            return self._handle_search_intent(msg)

        # 5. SUMMARIZE INTENT
        # e.g. "summarize my emails", "summarize latest emails"
        if "summarize" in msg_lower or "summary" in msg_lower:
            return self._handle_summarize_intent(msg)

        # 6. GENERAL / HELP INTENT
        return self._handle_help_intent(msg)

    def _handle_scrape_leads_intent(self, msg: str) -> Dict[str, Any]:
        """Handles autonomous lead scraping and CSV generation."""
        msg_lower = msg.lower()

        # Extract desired count (default 10)
        count_match = re.search(r"(\d+)\s+(?:roofers?|companies|agencies|contractors|leads)", msg_lower)
        count = int(count_match.group(1)) if count_match else 10
        count = max(1, min(count, 20))

        # Determine location (default Dallas, TX)
        location = "Dallas, TX"
        loc_match = re.search(r"(?:in|from)\s+([a-zA-Z\s]+)(?:who|that|for|\.|$)", msg, flags=re.IGNORECASE)
        if loc_match:
            cand = loc_match.group(1).strip()
            if cand.lower() not in ("the web", "google", "us", "usa", "csv"):
                location = cand if "tx" in cand.lower() or "texas" in cand.lower() else f"{cand}, TX"

        scraper = LeadScraper()

        # Check if IT agency or roofer/local business
        is_it = any(w in msg_lower for w in ["it ", "software", "contracting", "independent contractor", "developer"])
        
        try:
            if is_it:
                leads = scraper.find_it_companies(
                    query="IT consulting software development agency",
                    location=location,
                    count=count
                )
                csv_filename = "leads_it_agencies.csv"
                campaign_type = "it_contractor"
            else:
                # Default is local SMB without website (e.g. Dallas roofers)
                industry = "roofing contractors" if ("roof" in msg_lower or "roofer" in msg_lower) else "local contractors"
                leads = scraper.find_local_businesses(
                    industry=industry,
                    location=location,
                    count=count,
                    no_website_only=True
                )
                csv_filename = "leads_dallas_roofers.csv"
                campaign_type = "roofer_no_website"

            csv_path = scraper.export_to_csv(leads, csv_filename)

            # Generate sample outreach email for the first lead with email
            leads_with_email = [l for l in leads if l.get("email")]
            sample_preview = ""
            if leads_with_email:
                first = leads_with_email[0]
                draft = generate_outreach_email(
                    email=first["email"],
                    name=first.get("name"),
                    company=first.get("company"),
                    campaign_type=campaign_type
                )
                sample_preview = (
                    f"\n\n**Sample Outreach Draft (for {first['company']}):**\n"
                    f"• **Subject:** {draft['subject']}\n"
                    f"```\n{draft['body_text']}\n```"
                )

            # Build readable summary table
            summary_lines = [
                f"🎯 **Found {len(leads)} target businesses in {location}!**\n",
                f"📁 Saved and exported to: `{csv_path}`\n",
                f"**Discovered Leads:**"
            ]

            for i, l in enumerate(leads[:8], 1):
                status_icon = "❌ No Website" if not l.get("has_website") else f"🌐 {l.get('website')}"
                email_str = f"`{l['email']}`" if l.get("email") else "*(Search in progress)*"
                summary_lines.append(f"{i}. **{l['company']}** | Phone: `{l['phone']}` | {status_icon} | Email: {email_str}")

            if len(leads) > 8:
                summary_lines.append(f"\n*(and {len(leads) - 8} more saved to CSV...)*")

            summary_lines.append(sample_preview)
            summary_lines.append("\n💡 **Ready to reach out?** Reply **'Send to these leads'** or open the Web Dashboard to review before sending!")

            return {
                "response": "\n".join(summary_lines),
                "action": "leads_scraped",
                "data": {
                    "count": len(leads),
                    "leads": leads,
                    "csv_path": str(csv_path),
                    "campaign_type": campaign_type
                }
            }
        except Exception as e:
            return {
                "response": f"❌ Error scraping leads: {str(e)}",
                "action": "error",
                "data": {"error": str(e)}
            }

    def _handle_send_email_intent(self, msg: str, recipient_email: str) -> Dict[str, Any]:
        """Handles drafting and sending an email to the specified recipient."""
        notes = ""
        instruction_match = re.search(r"(?:and tell|telling|saying|say|about|with offer|offering|to build)\s+(.+)", msg, flags=re.IGNORECASE)
        if instruction_match:
            notes = instruction_match.group(1).strip()

        auto_send = any(w in msg.lower() for w in ["send it", "send now", "automatically", "and send", "go ahead and send"])

        name, company = infer_name_and_company(recipient_email)

        draft = generate_outreach_email(
            email=recipient_email,
            name=name if name != "there" else None,
            company=company if company != "your business" else None,
            custom_notes=notes or None
        )

        already_sent = self.sender.is_already_sent(recipient_email)

        if auto_send:
            send_res = self.sender.send_email(
                to_email=recipient_email,
                subject=draft["subject"],
                body_text=draft["body_text"],
                body_html=draft["body_html"],
                force=True
            )
            if send_res.get("success"):
                response_text = (
                    f"✅ **Email Sent Successfully to {recipient_email}!**\n\n"
                    f"• **Subject:** {draft['subject']}\n"
                    f"• **To:** {recipient_email}\n"
                    f"• **Status:** Dispatched via Gmail TLS\n\n"
                    f"**Message Preview:**\n```\n{draft['body_text']}\n```"
                )
                return {
                    "response": response_text,
                    "action": "email_sent",
                    "data": {
                        "to": recipient_email,
                        "subject": draft["subject"],
                        "body_text": draft["body_text"],
                        "status": "sent"
                    }
                }
            else:
                return {
                    "response": f"❌ **Failed to send email to {recipient_email}:** {send_res.get('error')}",
                    "action": "error",
                    "data": send_res
                }

        status_note = "*(⚠️ Note: You previously sent an email to this address)*" if already_sent else ""
        response_text = (
            f"I have prepared the email for **{recipient_email}**! {status_note}\n\n"
            f"**Subject:** {draft['subject']}\n\n"
            f"**Email Body:**\n"
            f"```\n{draft['body_text']}\n```\n\n"
            f"Would you like me to dispatch this now? You can reply **'Send it'** or click the send button."
        )

        return {
            "response": response_text,
            "action": "draft_created",
            "data": {
                "to": recipient_email,
                "name": name,
                "company": company,
                "subject": draft["subject"],
                "body_text": draft["body_text"],
                "body_html": draft["body_html"],
                "already_sent": already_sent
            }
        }

    def _handle_check_inbox_intent(self, msg: str) -> Dict[str, Any]:
        """Fetches and summarizes recent emails from the inbox."""
        count_match = re.search(r"(\d+)\s+emails?", msg)
        limit = int(count_match.group(1)) if count_match else 5
        limit = max(1, min(limit, 20))

        try:
            emails = self.reader.fetch_recent_emails(limit=limit)
            if not emails:
                return {
                    "response": "📭 Your inbox is empty or no recent messages were found.",
                    "action": "inbox_checked",
                    "data": {"emails": []}
                }

            summary = self.reader.summarize_emails(emails)
            response_text = f"📬 **Here are your {len(emails)} most recent emails:**\n\n{summary}"

            return {
                "response": response_text,
                "action": "inbox_checked",
                "data": {"count": len(emails), "emails": emails}
            }
        except Exception as e:
            return {
                "response": f"❌ Error reading inbox: {str(e)}",
                "action": "error",
                "data": {"error": str(e)}
            }

    def _handle_search_intent(self, msg: str) -> Dict[str, Any]:
        """Searches emails by sender, subject, or keyword."""
        from_address = None
        keyword = None

        from_match = re.search(r"from\s+([^\s,]+)", msg, flags=re.IGNORECASE)
        if from_match:
            from_address = from_match.group(1).strip()

        keyword_match = re.search(r"(?:about|mentioning|keyword|containing|with|for)\s+([^\s,]+)", msg, flags=re.IGNORECASE)
        if keyword_match:
            keyword = keyword_match.group(1).strip().strip("'\"")

        if not from_address and not keyword:
            cleaned = re.sub(r"(find|search|look for|emails?|in my inbox|in inbox)", "", msg, flags=re.IGNORECASE).strip()
            keyword = cleaned if cleaned else None

        try:
            results = self.reader.search_emails(
                query=keyword,
                from_address=from_address,
                subject_keyword=keyword,
                body_keyword=keyword,
                limit=6
            )

            if not results:
                target_desc = f"from '{from_address}'" if from_address else f"matching '{keyword}'"
                return {
                    "response": f"🔍 No emails found {target_desc} in your inbox.",
                    "action": "search_results",
                    "data": {"query": keyword, "from_address": from_address, "results": []}
                }

            summary = self.reader.summarize_emails(results)
            response_text = f"🔍 **Found {len(results)} matching email(s):**\n\n{summary}"

            return {
                "response": response_text,
                "action": "search_results",
                "data": {
                    "query": keyword,
                    "from_address": from_address,
                    "count": len(results),
                    "results": results
                }
            }
        except Exception as e:
            return {
                "response": f"❌ Error searching emails: {str(e)}",
                "action": "error",
                "data": {"error": str(e)}
            }

    def _handle_summarize_intent(self, msg: str) -> Dict[str, Any]:
        """Summarizes recent emails or emails from a specific sender."""
        from_match = re.search(r"from\s+([^\s,]+)", msg, flags=re.IGNORECASE)
        from_addr = from_match.group(1).strip() if from_match else None

        try:
            if from_addr:
                emails = self.reader.search_emails(from_address=from_addr, limit=5)
            else:
                emails = self.reader.fetch_recent_emails(limit=5)

            if not emails:
                return {
                    "response": "No emails found to summarize.",
                    "action": "summarize",
                    "data": {"emails": []}
                }

            summary = self.reader.summarize_emails(emails)
            return {
                "response": f"📊 **Email Summary:**\n\n{summary}",
                "action": "summarize",
                "data": {"emails": emails}
            }
        except Exception as e:
            return {
                "response": f"❌ Error summarizing emails: {str(e)}",
                "action": "error",
                "data": {"error": str(e)}
            }

    def _handle_help_intent(self, msg: str) -> Dict[str, Any]:
        """Help and general prompt response."""
        help_text = (
            "👋 **Hi! I am your Autonomous Email & Lead Copilot.**\n\n"
            "Here is what you can ask me to do:\n"
            "1. **Scrape Leads & Generate CSV:**\n"
            "   • *'Find 10 roofers from Dallas who don't have a website and fill up their contact details into CSV'*\n"
            "   • *'Find 10 IT companies in Dallas for contracting'*\n"
            "2. **Send an outreach email:**\n"
            "   • *'Email alex@acme.com and tell him I can build a website for $1'*\n"
            "   • *'Send email to founder@startup.io and send it now'*\n"
            "3. **Check incoming emails:**\n"
            "   • *'Check my inbox'* or *'Check my last 5 emails'*\n"
            "4. **Search specific emails:**\n"
            "   • *'Find emails from google'*\n"
            "   • *'Search emails about invoice'*"
        )
        return {
            "response": help_text,
            "action": "help",
            "data": {}
        }
