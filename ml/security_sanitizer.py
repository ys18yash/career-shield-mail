import re
import html
import unicodedata
from typing import Dict, Any, List

DANGEROUS_TAGS_RE = re.compile(r'<(script|iframe|object|embed|applet|style|meta|link|base)[^>]*>.*?</\1>', re.IGNORECASE | re.DOTALL)
DANGEROUS_ATTRIBUTES_RE = re.compile(r'\b(on\w+|javascript:|data:|vbscript:)\s*=', re.IGNORECASE)
HTML_TAGS_RE = re.compile(r'<[^>]+>')
URL_RE = re.compile(r'https?://[^\s<>"]+|www\.[^\s<>"]+', re.IGNORECASE)

MAX_EMAIL_BODY_LENGTH = 50000

def sanitize_email_text(raw_text: str, max_chars: int = MAX_EMAIL_BODY_LENGTH) -> str:
    """
    Sanitizes raw untrusted email text:
    - Normalizes Unicode representations (NFKC).
    - Removes dangerous executable markup (<script>, <iframe>, event handlers).
    - Converts HTML entities to clean text.
    - Strips residual HTML markup.
    - Truncates oversized payloads to prevent ReDoS/memory exhaustion.
    """
    if not raw_text or not isinstance(raw_text, str):
        return ""
    
    # 1. Truncate oversized input early
    if len(raw_text) > max_chars:
        raw_text = raw_text[:max_chars]
        
    # 2. Normalize Unicode
    normalized = unicodedata.normalize('NFKC', raw_text)
    
    # 3. Strip dangerous executable containers
    cleaned = DANGEROUS_TAGS_RE.sub(' ', normalized)
    cleaned = DANGEROUS_ATTRIBUTES_RE.sub(' ', cleaned)
    
    # 4. Convert HTML entities safely
    unescaped = html.unescape(cleaned)
    
    # 5. Strip all remaining HTML tags
    text_only = HTML_TAGS_RE.sub(' ', unescaped)
    
    # 6. Normalize whitespace
    text_only = re.sub(r'\s+', ' ', text_only).strip()
    return text_only


def extract_safe_urls(text: str) -> List[str]:
    """
    Safely extracts and sanitizes HTTP/HTTPS URLs from email body text.
    Rejects javascript:, data:, and malformed URI schemes.
    """
    if not text or not isinstance(text, str):
        return []
    
    raw_urls = URL_RE.findall(text)
    safe_urls = []
    for u in raw_urls:
        u_clean = u.strip().rstrip('.,;:)"\'>')
        if u_clean.lower().startswith(('http://', 'https://', 'www.')):
            # Defend against nested data/javascript payloads
            if not any(x in u_clean.lower() for x in ['javascript:', 'data:', '<script']):
                safe_urls.append(u_clean)
    return list(set(safe_urls))
