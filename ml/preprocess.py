import re
import numpy as np
import pandas as pd

FREE_EMAIL_DOMAINS = {
    'gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'protonmail.com',
    'proton.me', 'rediffmail.com', 'mail.com', 'zoho.com', 'yandex.com', 'gmx.com'
}

SUSPICIOUS_TLDS = {
    '.xyz', '.top', '.cc', '.site', '.online', '.club', '.biz', '.info',
    '.work', '.link', '.click', '.zip', '.mov', '.surf', '.space', '.bid'
}

FINANCIAL_TRIGGERS_STR = [
    r'(?:registration\s+fee|security\s+deposit|processing\s+fee|application\s+fee|onboarding\s+fee)',
    r'(?:access\s+fee|digital\s+id(?:\s+card)?|id\s+card\s+(?:fee|issuance|access|charges)|platform\s+access(?:\s+fee)?|lms\s+access)',
    r'(?:certificate\s+(?:fee|issuance|charges|cost)|verification\s+fee|exam\s+fee|course\s+fee|training\s+fee)',
    r'(?:kit\s+fee|activation\s+fee|seat\s+reservation\s+fee|slot\s+booking\s+fee|maintenance\s+fee|charge[s]?\s+(?:of|for|apply))',
    r'(?:pay\s+(?:rs\.?|₹|\$)?\s*\d+|transfer\s+(?:rs\.?|₹|\$)?\s*\d+|fee\s*:\s*(?:rs\.?|₹|\$)?\s*\d+|charge\s*:\s*(?:rs\.?|₹|\$)?\s*\d+|amount\s*:\s*(?:rs\.?|₹|\$)?\s*\d+|cost\s*:\s*(?:rs\.?|₹|\$)?\s*\d+|₹\s*\d+)',
    r'(?:upi|gpay|phonepe|paytm|bank\s+account\s+transfer|send\s+money|crypto|usdt)',
    r'(?:refundable\s+deposit|uniform\s+fee|laptop\s+deposit)',
    r'(?:no\s+internship\s+fee|not\s+an\s+internship\s+fee|charged\s+only\s+for\s+digital|not\s+comfortable\s+with\s+the\s+.*?fee)'
]
FINANCIAL_TRIGGERS = [re.compile(p, re.IGNORECASE) for p in FINANCIAL_TRIGGERS_STR]

URGENCY_TRIGGERS_STR = [
    r'(?:urgent|urgently|immediate|immediately|hurry|limited\s+slots)',
    r'(?:apply\s+today|within\s+\d+\s*(?:hours?|minutes?|mins?))',
    r'(?:expires\s+tonight|last\s+chance|instant\s+offer|direct\s+offer|final\s+call|final\s+hours)',
    r'(?:lowest\s+price|biggest\s+discount|extra\s+\d+%\s+off|coupon\s+code|use\s+code|offer\s+ends\s+@)',
    r'(?:claim\s+your\s+(?:spot|seat|free)|secure\s+your\s+seat|only\s+a\s+few\s+(?:trial\s+)?slots|going\s+fast)',
    r'(?:no\s+interview|guaranteed\s+job|100%\s+selection|100%\s+job\s+confirmation)',
    r'(?:\[update\]\s+your\s+application\s+has\s+been\s+accepted|we\'?d\s+love\s+to\s+have\s+you\s+represent|talk\s+to\s+a\s+counsellor)'
]
URGENCY_TRIGGERS = [re.compile(p, re.IGNORECASE) for p in URGENCY_TRIGGERS_STR]

COMMUNICATION_TRIGGERS_STR = [
    r'(?:whatsapp|telegram|t\.me|wa\.me|bit\.ly|tinyurl|forms\.gle)',
    r'(?:\+91\d{10}|\b\d{10}\b)',
    r'(?:emailclick\?q=|emailunsubscribe\?q=)'
]
COMMUNICATION_TRIGGERS = [re.compile(p, re.IGNORECASE) for p in COMMUNICATION_TRIGGERS_STR]

ACCREDITATION_TRIGGERS_STR = [
    r'(?:registered\s+(?:organization\s+)?under\s+mca|recognized\s+under\s+msme|aligned\s+with\s+aicte|iso\s+certified)',
    r'(?:letter\s+of\s+recommendation\s*\(based\s+on\s+performance\)|completion\s+certificate)'
]
ACCREDITATION_TRIGGERS = [re.compile(p, re.IGNORECASE) for p in ACCREDITATION_TRIGGERS_STR]

EMAIL_RE = re.compile(r'[\w\.-]+@([\w\.-]+)')
URL_RE = re.compile(r'https?://[^\s]+|(?:www\.)?[a-zA-Z0-9-]+\.[a-zA-Z]{2,}[^\s]*')
SHORT_URL_RE = re.compile(r'bit\.ly|tinyurl|forms\.gle|t\.me|wa\.me|link\.internshala\.com', re.IGNORECASE)
ATS_PORTAL_RE = re.compile(r'greenhouse\.io|lever\.co|freshteam\.com|ashbyhq\.com|recruitee\.com|keka\.com|careers\.', re.IGNORECASE)
MICRO_FEE_P1 = re.compile(r'(?:access\s+fee|digital\s+id|id\s+card\s+issuance|platform\s+access|no\s+internship\s+fee)', re.IGNORECASE)
MICRO_FEE_P2 = re.compile(r'(?:₹|rs\.?|inr|\d+)', re.IGNORECASE)
WALKIN_RE = re.compile(r'\b(walk-in|office address|tower \d+|tech park|sector \d+)\b', re.IGNORECASE)

TARGET_BRANDS = [
    'amazon', 'flipkart', 'tcs', 'infosys', 'wipro', 'hdfc', 'icici',
    'google', 'microsoft', 'reliance', 'jio', 'swiggy', 'zomato', 'deloitte',
    'tech mahindra', 'indigo', 'air india', 'accenture', 'paytm', 'blinkit', 'zepto',
    'maang', 'faang', 'internshala', 'upgrad', 'propeers'
]


def clean_text_for_nlp(text: str, max_chars: int = 4000) -> str:
    """Cleans text for TF-IDF vectorization while preserving semantic indicators."""
    if not isinstance(text, str):
        return ""
    if len(text) > max_chars:
        text = text[:max_chars]
    text = text.replace('₹', ' rupee ')
    text = re.sub(r'^Job Posting:\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def extract_linguistic_and_security_features(text: str) -> dict:
    """Extracts dense numerical features combining linguistic properties and cybersecurity signals."""
    if not isinstance(text, str):
        text = ""
    if len(text) > 10000:
        text = text[:10000]
        
    cleaned = clean_text_for_nlp(text)
    lower = text.lower()
    
    char_len = len(cleaned)
    words = cleaned.split()
    word_count = max(len(words), 1)
    
    uppercase_count = sum(1 for c in text if c.isupper())
    uppercase_ratio = uppercase_count / max(char_len, 1)
    digit_count = sum(1 for c in text if c.isdigit())
    digit_ratio = digit_count / max(char_len, 1)
    exclamation_count = text.count('!')
    question_count = text.count('?')
    avg_word_length = char_len / word_count
    
    unique_words = set(w.lower() for w in words)
    ttr = len(unique_words) / word_count
    
    emails = EMAIL_RE.findall(text)
    has_free_email = 0
    has_company_email = 0
    if emails:
        for domain in emails:
            d_lower = domain.lower()
            if any(free in d_lower for free in FREE_EMAIL_DOMAINS):
                has_free_email = 1
            else:
                has_company_email = 1
                
    urls = URL_RE.findall(text)
    url_count = len(urls)
    has_short_url = 1 if any(SHORT_URL_RE.search(u) for u in urls) else 0
    has_suspicious_tld = 1 if any(any(u.lower().endswith(tld) or (tld + '/') in u.lower() for tld in SUSPICIOUS_TLDS) for u in urls) else 0
    has_ats_portal = 1 if any(ATS_PORTAL_RE.search(u) for u in urls) else 0

    financial_score = sum(len(pat.findall(lower)) for pat in FINANCIAL_TRIGGERS)
    urgency_score = sum(len(pat.findall(lower)) for pat in URGENCY_TRIGGERS)
    comm_score = sum(len(pat.findall(lower)) for pat in COMMUNICATION_TRIGGERS)
    accreditation_score = sum(len(pat.findall(lower)) for pat in ACCREDITATION_TRIGGERS)
    
    has_micro_fee_trap = 1 if (
        MICRO_FEE_P1.search(lower) and MICRO_FEE_P2.search(lower)
    ) else 0

    brand_mentions = sum(1 for b in TARGET_BRANDS if b in lower)
    spoof_risk_flag = 1 if (brand_mentions > 0 and (has_free_email or has_short_url or financial_score > 0 or has_micro_fee_trap > 0)) else 0
    
    has_walkin_address = 1 if WALKIN_RE.search(lower) else 0
    
    return {
        'char_len': char_len,
        'word_count': word_count,
        'uppercase_ratio': uppercase_ratio,
        'digit_ratio': digit_ratio,
        'exclamation_count': exclamation_count,
        'question_count': question_count,
        'avg_word_length': avg_word_length,
        'type_token_ratio': ttr,
        'has_free_email': has_free_email,
        'has_company_email': has_company_email,
        'url_count': url_count,
        'has_short_url': has_short_url,
        'has_suspicious_tld': has_suspicious_tld,
        'has_ats_portal': has_ats_portal,
        'financial_score': financial_score,
        'urgency_score': urgency_score,
        'comm_score': comm_score,
        'accreditation_score': accreditation_score,
        'has_micro_fee_trap': has_micro_fee_trap,
        'brand_mentions': brand_mentions,
        'spoof_risk_flag': spoof_risk_flag,
        'has_walkin_address': has_walkin_address
    }


def extract_features_df(texts: list) -> pd.DataFrame:
    """Extracts DataFrame of features for a list of texts."""
    rows = [extract_linguistic_and_security_features(t) for t in texts]
    return pd.DataFrame(rows)
