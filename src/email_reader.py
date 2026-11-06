import email
from email.header import decode_header
from email.message import Message
import imaplib
import os
import re
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

def decode_header_str(header_val: Optional[str]) -> str:
    """Decode RFC 2047 encoded email header to Unicode string."""
    if not header_val:
        return ""
    try:
        decoded_parts = decode_header(header_val)
        result = []
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                encoding = encoding or "utf-8"
                try:
                    result.append(part.decode(encoding, errors="replace"))
                except Exception:
                    result.append(part.decode("utf-8", errors="replace"))
            else:
                result.append(str(part))
        return "".join(result)
    except Exception:
        return str(header_val)

def clean_html_to_text(html_content: str) -> str:
    """Basic HTML tag stripping and formatting for email bodies."""
    # Remove script and style elements
    text = re.sub(r"<(script|style).*?</\1>", "", html_content, flags=re.DOTALL | re.IGNORECASE)
    # Replace line breaks and paragraph ends with newlines
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
    # Remove all other HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Clean up excess whitespace
    lines = [line.strip() for line in text.split("\n")]
    return "\n".join([line for line in lines if line])

class EmailReader:
    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        user: Optional[str] = None,
        password: Optional[str] = None
    ):
        self.host = host or os.getenv("IMAP_HOST", "imap.gmail.com")
        self.port = int(port or os.getenv("IMAP_PORT", 993))
        self.user = user or os.getenv("SMTP_USER", "")
        self.password = (password or os.getenv("SMTP_PASSWORD", "")).replace(" ", "")

    def _connect(self) -> imaplib.IMAP4_SSL:
        """Establish SSL connection and log in to IMAP server."""
        if not self.user or not self.password:
            raise ValueError("IMAP credentials missing. Please check SMTP_USER and SMTP_PASSWORD in .env.")
        mail = imaplib.IMAP4_SSL(self.host, self.port)
        mail.login(self.user, self.password)
        return mail

    def _extract_body_and_snippet(self, msg: Message) -> tuple[str, str]:
        """Extract plain text body and a clean short snippet from an email message."""
        body_text = ""
        body_html = ""

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))

                if "attachment" in content_disposition:
                    continue

                try:
                    payload = part.get_payload(decode=True)
                    if not payload:
                        continue
                    charset = part.get_content_charset() or "utf-8"
                    decoded_text = payload.decode(charset, errors="replace")

                    if content_type == "text/plain":
                        body_text += decoded_text + "\n"
                    elif content_type == "text/html":
                        body_html += decoded_text + "\n"
                except Exception:
                    continue
        else:
            try:
                payload = msg.get_payload(decode=True)
                charset = msg.get_content_charset() or "utf-8"
                if payload:
                    body_text = payload.decode(charset, errors="replace")
            except Exception:
                body_text = str(msg.get_payload())

        # If no plain text was found, convert HTML to text
        final_text = body_text.strip() if body_text.strip() else clean_html_to_text(body_html)
        # Create a 150-char clean snippet
        snippet = re.sub(r"\s+", " ", final_text).strip()[:180]
        if len(final_text) > 180:
            snippet += "..."

        return final_text, snippet

    def fetch_recent_emails(self, limit: int = 10, folder: str = "INBOX") -> List[Dict[str, Any]]:
        """Fetch the most recent N emails from the specified mailbox."""
        mail = self._connect()
        try:
            mail.select(folder, readonly=True)
            status, data = mail.search(None, "ALL")
            if status != "OK" or not data or not data[0]:
                return []

            mail_ids = data[0].split()
            # Most recent first
            recent_ids = mail_ids[-limit:][::-1]

            results = []
            for m_id in recent_ids:
                status, msg_data = mail.fetch(m_id, "(RFC822)")
                if status != "OK" or not msg_data:
                    continue

                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        raw_msg = email.message_from_bytes(response_part[1])
                        subject = decode_header_str(raw_msg.get("Subject", "(No Subject)"))
                        from_hdr = decode_header_str(raw_msg.get("From", ""))
                        to_hdr = decode_header_str(raw_msg.get("To", ""))
                        date_hdr = raw_msg.get("Date", "")
                        body, snippet = self._extract_body_and_snippet(raw_msg)

                        # Extract sender email address
                        email_match = re.search(r"[\w\.-]+@[\w\.-]+", from_hdr)
                        sender_email = email_match.group(0) if email_match else from_hdr

                        results.append({
                            "id": m_id.decode("utf-8") if isinstance(m_id, bytes) else str(m_id),
                            "subject": subject,
                            "from": from_hdr,
                            "from_email": sender_email,
                            "to": to_hdr,
                            "date": date_hdr,
                            "snippet": snippet,
                            "body": body[:2000] # Cap body size for performance
                        })
            return results
        finally:
            try:
                mail.close()
                mail.logout()
            except Exception:
                pass

    def search_emails(
        self,
        query: Optional[str] = None,
        from_address: Optional[str] = None,
        subject_keyword: Optional[str] = None,
        body_keyword: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search emails using IMAP search criteria combined with client-side regex matching.
        """
        mail = self._connect()
        try:
            mail.select("INBOX", readonly=True)

            search_criteria = []
            if from_address:
                search_criteria.append(f'FROM "{from_address}"')
            if subject_keyword:
                search_criteria.append(f'SUBJECT "{subject_keyword}"')
            if body_keyword:
                search_criteria.append(f'BODY "{body_keyword}"')
            if query and not (from_address or subject_keyword or body_keyword):
                # General query: check text or recent messages
                search_criteria.append(f'TEXT "{query}"')

            imap_query = " ".join(search_criteria) if search_criteria else "ALL"

            status, data = mail.search(None, imap_query)
            if status != "OK" or not data or not data[0]:
                # If specific IMAP TEXT failed (some IMAP servers are picky), fetch recent 50 and search locally
                status, data = mail.search(None, "ALL")
                fallback_local_search = True
            else:
                fallback_local_search = False

            if not data or not data[0]:
                return []

            mail_ids = data[0].split()
            # If local fallback, take last 50 emails to filter
            if fallback_local_search:
                mail_ids = mail_ids[-50:]

            # Most recent first
            target_ids = mail_ids[::-1]
            matches = []

            for m_id in target_ids:
                if len(matches) >= limit:
                    break

                status, msg_data = mail.fetch(m_id, "(RFC822)")
                if status != "OK" or not msg_data:
                    continue

                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        raw_msg = email.message_from_bytes(response_part[1])
                        subject = decode_header_str(raw_msg.get("Subject", "(No Subject)"))
                        from_hdr = decode_header_str(raw_msg.get("From", ""))
                        to_hdr = decode_header_str(raw_msg.get("To", ""))
                        date_hdr = raw_msg.get("Date", "")
                        body, snippet = self._extract_body_and_snippet(raw_msg)

                        email_match = re.search(r"[\w\.-]+@[\w\.-]+", from_hdr)
                        sender_email = email_match.group(0) if email_match else from_hdr

                        # Apply local filters if needed
                        q_lower = (query or "").lower()
                        from_lower = (from_address or "").lower()
                        subj_lower = (subject_keyword or "").lower()
                        body_lower = (body_keyword or "").lower()

                        matched = True
                        if from_lower and from_lower not in from_hdr.lower():
                            matched = False
                        if subj_lower and subj_lower not in subject.lower():
                            matched = False
                        if body_lower and body_lower not in body.lower():
                            matched = False
                        if q_lower and fallback_local_search:
                            if q_lower not in subject.lower() and q_lower not in body.lower() and q_lower not in from_hdr.lower():
                                matched = False

                        if matched:
                            matches.append({
                                "id": m_id.decode("utf-8") if isinstance(m_id, bytes) else str(m_id),
                                "subject": subject,
                                "from": from_hdr,
                                "from_email": sender_email,
                                "to": to_hdr,
                                "date": date_hdr,
                                "snippet": snippet,
                                "body": body[:2000]
                            })
            return matches
        finally:
            try:
                mail.close()
                mail.logout()
            except Exception:
                pass

    def summarize_emails(self, emails: List[Dict[str, Any]]) -> str:
        """Create a clean, human-readable summary of a list of emails."""
        if not emails:
            return "No emails found to summarize."

        summary_lines = [f"Found {len(emails)} email(s):"]
        for i, em in enumerate(emails, 1):
            sender = em.get("from_email") or em.get("from")
            subject = em.get("subject", "(No Subject)")
            date = em.get("date", "").split(" +")[0].split(" -")[0]
            snippet = em.get("snippet", "").strip()

            summary_lines.append(f"\n{i}. **{subject}**")
            summary_lines.append(f"   • **From:** {sender}")
            if date:
                summary_lines.append(f"   • **Date:** {date}")
            if snippet:
                summary_lines.append(f"   • **Summary:** {snippet}")

        return "\n".join(summary_lines)
