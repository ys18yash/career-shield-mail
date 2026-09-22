import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
import re
import html
import threading
import time
from datetime import datetime
from typing import List, Dict, Optional, Any
import socket
import ssl

from ml.security_sanitizer import sanitize_email_text

def decode_str(s) -> str:
    """Decodes MIME encoded header strings (e.g., =?utf-8?B?...?=)."""
    if not s:
        return ""
    try:
        decoded_fragments = decode_header(s)
        result = []
        for fragment, encoding in decoded_fragments:
            if isinstance(fragment, bytes):
                try:
                    result.append(fragment.decode(encoding or 'utf-8', errors='ignore'))
                except Exception:
                    result.append(fragment.decode('latin1', errors='ignore'))
            else:
                result.append(str(fragment))
        return "".join(result).strip()
    except Exception:
        return str(s)


def extract_body_from_message(msg) -> str:
    """Extracts clean plaintext body from an email.message object with security sanitization."""
    body_text = ""
    html_text = ""

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in content_disposition:
                continue

            try:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or 'utf-8'
                    try:
                        decoded_part = payload.decode(charset, errors='ignore')
                    except Exception:
                        try:
                            decoded_part = payload.decode('utf-8', errors='ignore')
                        except Exception:
                            decoded_part = payload.decode('latin1', errors='ignore')

                    if content_type == "text/plain":
                        body_text += decoded_part + "\n"
                    elif content_type == "text/html":
                        html_text += decoded_part + "\n"
            except Exception:
                continue
    else:
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or 'utf-8'
                try:
                    decoded_part = payload.decode(charset, errors='ignore')
                except Exception:
                    decoded_part = payload.decode('utf-8', errors='ignore')
                if msg.get_content_type() == "text/html":
                    html_text = decoded_part
                else:
                    body_text = decoded_part
        except Exception:
            body_text = str(msg.get_payload() or "")

    raw_combined = body_text.strip() or html_text.strip()
    return sanitize_email_text(raw_combined, max_chars=35000)


class GmailClient:
    """Production-grade IMAP SSL Gmail Client with UID search, All Mail sync, and chronological sorting."""
    def __init__(self, email_address: str, app_password: str, is_mock: bool = False):
        self.email_address = email_address.strip()
        self.app_password = app_password.replace(" ", "").strip()
        self.imap_server = "imap.gmail.com"
        self.imap_port = 993
        self.timeout = 25
        self.is_mock = is_mock or (self.email_address.lower() == "mock@example.com")
        self._lock = threading.Lock()

    def test_connection(self) -> bool:
        """Validates credentials against IMAP SSL without modifying inbox state."""
        if self.is_mock:
            return True
        with self._lock:
            try:
                mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port, timeout=self.timeout)
                mail.login(self.email_address, self.app_password)
                mail.logout()
                return True
            except imaplib.IMAP4.error as e:
                raise ValueError(f"Gmail IMAP Authentication Failed: {str(e)}. Please ensure you are using a 16-character Google App Password with 2FA enabled.")
            except Exception as e:
                raise ConnectionError(f"Network error connecting to Gmail IMAP server ({self.imap_server}): {str(e)}")

    def fetch_latest_emails(self, folder: str = "INBOX", limit: int = 100) -> List[Dict[str, Any]]:
        """Fetches the latest email messages using IMAP UID search and sorts strictly chronologically."""
        if self.is_mock:
            return self._generate_mock_emails(limit)

        with self._lock:
            mail = None
            try:
                mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port, timeout=self.timeout)
                mail.login(self.email_address, self.app_password)
                
                target_folder = folder
                if folder.upper() in ["ALL", "ALL MAIL", "[GMAIL]/ALL MAIL"]:
                    target_folder = '"[Gmail]/All Mail"'
                elif folder.upper() in ["SPAM", "[GMAIL]/SPAM"]:
                    target_folder = '"[Gmail]/Spam"'
                elif folder.upper() in ["SENT", "[GMAIL]/SENT MAIL"]:
                    target_folder = '"[Gmail]/Sent Mail"'

                status, _ = mail.select(target_folder, readonly=True)
                if status != "OK":
                    status, _ = mail.select('"[Gmail]/All Mail"', readonly=True)
                    if status != "OK":
                        status, _ = mail.select("INBOX", readonly=True)
                        if status != "OK":
                            raise ValueError(f"Could not open mail folder: {folder}")

                status, data = mail.uid('search', None, "ALL")
                if status != "OK" or not data or not data[0]:
                    return []

                uid_list = data[0].split()
                try:
                    uid_list = sorted(uid_list, key=lambda x: int(x))
                except Exception:
                    pass

                selected_uids = uid_list[-limit:] if len(uid_list) > limit else uid_list
                selected_uids = selected_uids[::-1]

                emails_list = []
                for uid_b in selected_uids:
                    uid_str = uid_b.decode('utf-8', errors='ignore')
                    try:
                        res, msg_data = mail.uid('fetch', uid_b, "(BODY.PEEK[])")
                        if res != "OK" or not msg_data:
                            continue

                        raw_email = None
                        for response_part in msg_data:
                            if isinstance(response_part, tuple) and len(response_part) >= 2:
                                raw_email = response_part[1]
                                break

                        if not raw_email:
                            continue

                        msg = email.message_from_bytes(raw_email)
                        subject = decode_str(msg.get("Subject", "(No Subject)"))
                        from_header = decode_str(msg.get("From", "(Unknown Sender)"))
                        to_header = decode_str(msg.get("To", ""))
                        cc_header = decode_str(msg.get("Cc", ""))
                        date_str = decode_str(msg.get("Date", ""))
                        message_id = msg.get("Message-ID", f"gmail-{uid_str}")

                        sender_name = from_header
                        sender_email = from_header
                        if "<" in from_header and ">" in from_header:
                            parts = from_header.split("<", 1)
                            sender_name = parts[0].strip().strip('"')
                            sender_email = parts[1].split(">", 1)[0].strip()

                        timestamp_epoch = time.time()
                        iso_date = datetime.utcnow().isoformat()
                        if date_str:
                            try:
                                dt = parsedate_to_datetime(date_str)
                                timestamp_epoch = dt.timestamp()
                                iso_date = dt.isoformat()
                            except Exception:
                                pass

                        body_text = extract_body_from_message(msg)

                        emails_list.append({
                            "id": f"gmail-uid-{uid_str}",
                            "message_id": message_id,
                            "sender_name": sender_name or sender_email,
                            "sender_email": sender_email,
                            "recipient": to_header or self.email_address,
                            "cc": cc_header,
                            "subject": subject,
                            "date": date_str or datetime.now().strftime("%a, %d %b %Y %H:%M:%S"),
                            "timestamp": iso_date,
                            "timestamp_epoch": timestamp_epoch,
                            "is_read": False,
                            "is_starred": False,
                            "category": folder,
                            "body": body_text if body_text else subject
                        })
                    except Exception as parse_err:
                        continue

                emails_list.sort(key=lambda x: x.get("timestamp_epoch", 0), reverse=True)
                return emails_list
            finally:
                if mail:
                    try:
                        mail.close()
                        mail.logout()
                    except Exception:
                        pass

    def disconnect(self):
        """Cleans up session."""
        pass

    def _generate_mock_emails(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Provides realistic mock email items for offline testing and CI environments."""
        return [
            {
                "id": "mock-gmail-01",
                "message_id": "<mock-01@gmail.com>",
                "sender_name": "SkillInfyTech Recruitment Team",
                "sender_email": "hr@skillinfytech-careers.online",
                "subject": "Offer Letter: Software Engineering Internship - ID Card Access Fee",
                "date": datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0530"),
                "timestamp": datetime.utcnow().isoformat(),
                "timestamp_epoch": time.time(),
                "is_read": False,
                "is_starred": False,
                "category": "INBOX",
                "body": "Greetings from SkillInfyTech IT Solutions Private Limited. We are pleased to inform you about our 4-Weeks Internship Program. Internship Fee: No internship fee. Access Fee: ₹89 only (for Digital ID Card & platform access). Payment via UPI or GPay to verify your slot."
            },
            {
                "id": "mock-gmail-02",
                "message_id": "<mock-02@gmail.com>",
                "sender_name": "Google University Programs",
                "sender_email": "no-reply@careers.google.com",
                "subject": "Google Summer SWE Internship - Offer Details & Documentation",
                "date": datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0530"),
                "timestamp": datetime.utcnow().isoformat(),
                "timestamp_epoch": time.time() - 3600,
                "is_read": False,
                "is_starred": False,
                "category": "INBOX",
                "body": "Dear Candidate, We are thrilled to extend an offer for the Software Engineering Intern role in Bangalore with Google India. Monthly stipend INR 1,15,000. Review your offer package on careers.google.com."
            }
        ][:limit]
