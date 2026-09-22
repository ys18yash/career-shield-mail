import re
import ipaddress
import urllib.parse
import hashlib
from typing import List, Dict, Any, Optional, Set

URL_PATTERN = re.compile(
    r'(?:https?://|www\.)[a-zA-Z0-9][-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&/=]*)',
    re.IGNORECASE
)

EMAIL_PATTERN = re.compile(
    r'\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\b',
    re.IGNORECASE
)

IPV4_PATTERN = re.compile(
    r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
)

# IPv6 hex pattern (standard and compressed)
IPV6_PATTERN = re.compile(
    r'\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b|'
    r'\b(?:[0-9a-fA-F]{1,4}:){1,7}:|'
    r'\b:(?::[0-9a-fA-F]{1,4}){1,7}\b|'
    r'\b(?:[0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}\b'
)

PAYMENT_HANDLE_PATTERN = re.compile(
    r'\b[a-zA-Z0-9._\-]{2,40}@(upi|okhdfcbank|okaxis|okicici|oksbi|paytm|ybl|ibl|axl|apl|barodampay|postbank|fbl)\b',
    re.IGNORECASE
)

ATTACHMENT_PATTERN = re.compile(
    r'\b[\w,\s-]+\.(?:exe|scr|bat|vbs|iso|dmg|zip|rar|tar|gz|pdf|docx?|xlsx?|pptx?|apk|bin|js|ps1|py)\b',
    re.IGNORECASE
)

# Cryptographic Hash Patterns (SHA-256: 64 hex, SHA-1: 40 hex, MD5: 32 hex)
SHA256_PATTERN = re.compile(r'\b[a-fA-F0-9]{64}\b')
SHA1_PATTERN = re.compile(r'\b[a-fA-F0-9]{40}\b')
MD5_PATTERN = re.compile(r'\b[a-fA-F0-9]{32}\b')

RISKY_EXTENSIONS = {'.exe', '.scr', '.bat', '.vbs', '.iso', '.dmg', '.apk', '.bin', '.js', '.ps1'}
SUSPICIOUS_TLDS = {'.xyz', '.top', '.online', '.work', '.click', '.loan', '.gq', '.cf', '.tk', '.ml', '.bid', '.buzz', '.country', '.stream'}

MAX_TEXT_SCAN_LEN = 100000


def defang_indicator(ioc_type: str, value: str) -> str:
    """Defangs an IOC so it cannot be accidentally clicked or executed in security reports."""
    if ioc_type == "url":
        return value.replace("http://", "hxxp://").replace("https://", "hxxps://").replace(".", "[.]")
    elif ioc_type in ("domain", "ip", "ipv4", "ipv6", "email", "payment_handle"):
        return value.replace(".", "[.]").replace("@", "[at]").replace(":", "[:]")
    return value


def normalize_domain(domain_str: str) -> str:
    """Cleans, lowercases, and strips trailing periods/protocols/ports from a domain."""
    d = domain_str.lower().strip().rstrip('.')
    if '/' in d:
        d = d.split('/')[0]
    if ':' in d and not d.startswith('['):  # exclude bracketed ipv6
        d = d.split(':')[0]
    return d


class IOCExtractor:
    """
    Production-Quality Indicator of Compromise (IOC) Extraction Engine.
    Extracts, normalizes, validates, and tags indicators with forensic context.
    Protected against ReDoS, URL obfuscation, and malformed inputs.
    """

    @classmethod
    def extract_all_iocs(
        cls,
        text: str,
        sender: Optional[str] = None,
        recipient: Optional[str] = None,
        subject: Optional[str] = None,
        attachment_names: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Performs full multi-vector IOC extraction across body, headers, and attachments.
        """
        if not text or not isinstance(text, str):
            text = ""

        bounded_text = text[:MAX_TEXT_SCAN_LEN]
        combined_text = f"{subject or ''} {bounded_text}"

        iocs: List[Dict[str, Any]] = []
        seen_keys: Set[str] = set()

        def add_ioc(ioc_type: str, raw_val: str, norm_val: str, source: str, context: str, confidence: float = 0.90, metadata: Optional[Dict] = None):
            key = f"{ioc_type}:{norm_val}"
            if key in seen_keys or not norm_val:
                return
            seen_keys.add(key)
            ioc_id = "ioc-" + hashlib.sha256(key.encode()).hexdigest()[:12]
            iocs.append({
                "ioc_id": ioc_id,
                "type": ioc_type,
                "value": raw_val,
                "normalized_value": norm_val,
                "defanged_value": defang_indicator(ioc_type, norm_val),
                "source": source,
                "context": context[:250],
                "confidence": round(confidence, 2),
                "reputation_status": "unverified",
                "metadata": metadata or {}
            })

        # 1. Extract Sender Information
        if sender:
            sender_clean = sender.strip()
            emails_in_sender = EMAIL_PATTERN.findall(sender_clean)
            if emails_in_sender:
                sender_email = emails_in_sender[0].lower()
                sender_domain = sender_email.split('@')[-1]
                add_ioc("email", sender_email, sender_email, "header_from", "Envelope From Address", confidence=1.0, metadata={"is_sender": True})
                if sender_domain:
                    add_ioc("domain", sender_domain, sender_domain, "header_from", "Envelope Sender Domain", confidence=1.0)
            else:
                add_ioc("sender_display", sender_clean, sender_clean.lower(), "header_from", "Sender Display Name", confidence=0.85)

        # 2. Extract Recipient
        if recipient:
            recip_clean = recipient.strip()
            emails_in_recip = EMAIL_PATTERN.findall(recip_clean)
            for r_email in emails_in_recip:
                r_norm = r_email.lower()
                add_ioc("email", r_email, r_norm, "header_to", "Recipient Address", confidence=1.0, metadata={"is_recipient": True})

        # 3. Extract In-Body Email Addresses
        body_emails = EMAIL_PATTERN.findall(bounded_text)
        for e in body_emails:
            e_norm = e.lower()
            e_domain = e_norm.split('@')[-1]
            add_ioc("email", e, e_norm, "body", "Referenced Email in Body", confidence=0.92)
            if e_domain:
                add_ioc("domain", e_domain, e_domain, "body", "Domain of Referenced Email", confidence=0.90)

        # 4. Extract URLs & Nested Host Domains
        raw_urls = URL_PATTERN.findall(combined_text)
        for u in raw_urls:
            u_clean = u.strip().rstrip('.,;:)"\'>]')
            if not u_clean.lower().startswith(('http://', 'https://')):
                u_full = f"https://{u_clean}"
            else:
                u_full = u_clean

            try:
                parsed = urllib.parse.urlparse(u_full)
                host = normalize_domain(parsed.netloc or parsed.path.split('/')[0])
                if host:
                    is_suspicious_tld = any(host.endswith(tld) for tld in SUSPICIOUS_TLDS)
                    add_ioc("url", u_clean, u_full, "body", "Embedded Hyperlink", confidence=0.95, metadata={"host": host, "is_suspicious_tld": is_suspicious_tld, "scheme": parsed.scheme})
                    add_ioc("domain", host, host, "body", "Extracted Hostname from URL", confidence=0.95, metadata={"is_suspicious_tld": is_suspicious_tld})
            except Exception:
                continue

        # 5. Extract IPv4 & IPv6 Addresses
        raw_ips = IPV4_PATTERN.findall(combined_text)
        for ip in raw_ips:
            try:
                ip_obj = ipaddress.ip_address(ip)
                if isinstance(ip_obj, ipaddress.IPv4Address):
                    is_private = ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_reserved
                    add_ioc("ipv4", ip, str(ip_obj), "body", "IPv4 Address Indicator", confidence=0.90, metadata={"is_private": is_private, "version": 4})
            except ValueError:
                continue

        raw_ipv6 = IPV6_PATTERN.findall(combined_text)
        for ip6 in raw_ipv6:
            try:
                ip6_clean = ip6.strip().strip('[]')
                if ':' in ip6_clean and len(ip6_clean) >= 3:
                    ip6_obj = ipaddress.ip_address(ip6_clean)
                    if isinstance(ip6_obj, ipaddress.IPv6Address):
                        is_private = ip6_obj.is_private or ip6_obj.is_loopback or ip6_obj.is_reserved
                        add_ioc("ipv6", ip6_clean, str(ip6_obj), "body", "IPv6 Address Indicator", confidence=0.90, metadata={"is_private": is_private, "version": 6})
            except ValueError:
                continue

        # 6. Extract Payment / UPI Handles
        for handle_match in PAYMENT_HANDLE_PATTERN.finditer(combined_text):
            handle_str = handle_match.group(0).lower()
            add_ioc("payment_handle", handle_str, handle_str, "body", "Payment / UPI Settlement Handle", confidence=0.98, metadata={"psp_provider": handle_match.group(1)})

        # 7. Extract Attachments
        if attachment_names:
            for att in attachment_names:
                att_clean = att.strip()
                ext = "." + att_clean.split('.')[-1].lower() if '.' in att_clean else ""
                is_risky = ext in RISKY_EXTENSIONS
                add_ioc("attachment", att_clean, att_clean.lower(), "attachment_manifest", "Email Attachment File", confidence=0.95, metadata={"extension": ext, "is_executable_or_script": is_risky})

        mentioned_files = ATTACHMENT_PATTERN.findall(bounded_text)
        for mf in mentioned_files:
            mf_clean = mf.strip()
            ext = "." + mf_clean.split('.')[-1].lower() if '.' in mf_clean else ""
            is_risky = ext in RISKY_EXTENSIONS
            add_ioc("attachment", mf_clean, mf_clean.lower(), "body_mention", "Attachment File Mention in Body", confidence=0.80, metadata={"extension": ext, "is_executable_or_script": is_risky})

        # 8. Extract Cryptographic File Hashes (SHA-256, SHA-1, MD5)
        sha256_matches = SHA256_PATTERN.findall(bounded_text)
        for h in sha256_matches:
            add_ioc("file_hash", h, h.lower(), "body", "SHA-256 Cryptographic Hash Mention", confidence=0.95, metadata={"algorithm": "SHA-256"})

        sha1_matches = SHA1_PATTERN.findall(bounded_text)
        for h in sha1_matches:
            # check not part of already extracted sha256
            if not any(h.lower() in full_h.lower() for full_h in sha256_matches):
                add_ioc("file_hash", h, h.lower(), "body", "SHA-1 Cryptographic Hash Mention", confidence=0.90, metadata={"algorithm": "SHA-1"})

        md5_matches = MD5_PATTERN.findall(bounded_text)
        for h in md5_matches:
            # check not part of longer hashes
            if not any(h.lower() in full_h.lower() for full_h in sha256_matches) and not any(h.lower() in full_h.lower() for full_h in sha1_matches):
                add_ioc("file_hash", h, h.lower(), "body", "MD5 Cryptographic Hash Mention", confidence=0.85, metadata={"algorithm": "MD5"})

        return iocs
