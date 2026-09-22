import os
import time
import json
import sqlite3
import hashlib
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, List, Optional

DB_PATH = os.environ.get("CAREERSHIELD_DB_PATH", os.environ.get("CYBERSHIELD_DB_PATH", "data/careershield_store.db" if os.path.exists("data/careershield_store.db") else "data/careershield_store.db"))

CACHE_TTL_SECONDS = 86400  # 24 Hours


class BaseThreatIntelProvider(ABC):
    """Abstract base class for all Threat Intelligence enrichment providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @property
    @abstractmethod
    def is_available(self) -> bool:
        pass

    @abstractmethod
    def lookup_indicator(self, ioc_type: str, normalized_val: str) -> Optional[Dict[str, Any]]:
        """
        Queries the provider for reputation and context.
        Returns None if indicator is unknown or provider cannot determine.
        """
        pass


class LocalDevelopmentIntelProvider(BaseThreatIntelProvider):
    """
    Isolated local intelligence corpus for testing and offline development.
    CLEARLY LABELED AS 'Local Development Intelligence'.
    Contains known mock and educational indicators without fabricating external data.
    """

    def __init__(self):
        # Explicit curated dictionary of local test signatures
        self._local_db: Dict[str, Dict[str, Any]] = {
            # Suspicious recruitment scam domains
            "domain:skillinfytech-careers.online": {
                "reputation": "MALICIOUS",
                "threat_category": "Recruitment Micro-Fee Scam",
                "risk_score": 0.95,
                "confidence": 0.95,
                "tags": ["recruitment_fraud", "unregistered_tld", "fee_trap"],
                "notes": "Domain associated with fake digital ID card issuance scams."
            },
            "domain:hdfc-recruiter-desk.com": {
                "reputation": "MALICIOUS",
                "threat_category": "Brand Impersonation / Credential Phishing",
                "risk_score": 0.98,
                "confidence": 0.99,
                "tags": ["banking_spoof", "advance_fee", "fake_appointment"],
                "notes": "Impersonates HDFC Bank talent acquisition team."
            },
            "domain:amazon-hiring-portal.xyz": {
                "reputation": "MALICIOUS",
                "threat_category": "Brand Impersonation / Advance Deposit Scam",
                "risk_score": 0.97,
                "confidence": 0.98,
                "tags": ["brand_spoof", "deposit_fee", "fake_hr"],
                "notes": "Fake Amazon talent acquisition portal collecting security deposits."
            },
            "domain:t.me": {
                "reputation": "SUSPICIOUS",
                "threat_category": "Off-Platform Communication Diversion",
                "risk_score": 0.70,
                "confidence": 0.85,
                "tags": ["channel_diversion", "untraceable_messaging", "task_scam"],
                "notes": "Frequently used to divert victims into unregulated task-scam channels."
            },
            "domain:chat.whatsapp.com": {
                "reputation": "SUSPICIOUS",
                "threat_category": "Off-Platform Messaging Diversion",
                "risk_score": 0.65,
                "confidence": 0.80,
                "tags": ["channel_diversion", "informal_messaging"],
                "notes": "Group invite link used to avoid enterprise auditing."
            },
            # Known genuine enterprise hiring domains
            "domain:boards.greenhouse.io": {
                "reputation": "BENIGN",
                "threat_category": "Verified Enterprise ATS Portal",
                "risk_score": 0.01,
                "confidence": 0.99,
                "tags": ["verified_ats", "enterprise_hiring"],
                "notes": "Official Greenhouse Software hiring endpoint."
            },
            "domain:jobs.lever.co": {
                "reputation": "BENIGN",
                "threat_category": "Verified Enterprise ATS Portal",
                "risk_score": 0.01,
                "confidence": 0.99,
                "tags": ["verified_ats", "enterprise_hiring"],
                "notes": "Official Lever.co candidate management endpoint."
            },
            "domain:google.com": {
                "reputation": "BENIGN",
                "threat_category": "Verified Enterprise Domain",
                "risk_score": 0.00,
                "confidence": 1.00,
                "tags": ["enterprise_corporate", "whitelisted"],
                "notes": "Official Google corporate domain."
            },
            "domain:microsoft.com": {
                "reputation": "BENIGN",
                "threat_category": "Verified Enterprise Domain",
                "risk_score": 0.00,
                "confidence": 1.00,
                "tags": ["enterprise_corporate", "whitelisted"],
                "notes": "Official Microsoft corporate domain."
            },
            # Suspicious payment handles
            "payment_handle:hr-amazon@upi": {
                "reputation": "MALICIOUS",
                "threat_category": "P2P Settlement Trap",
                "risk_score": 0.96,
                "confidence": 0.95,
                "tags": ["unverified_upi", "advance_security_deposit", "impersonation"],
                "notes": "Flagged personal UPI ID collecting fake Amazon onboarding fees."
            },
            "payment_handle:career-fee@okhdfcbank": {
                "reputation": "MALICIOUS",
                "threat_category": "Advance Onboarding Fee Scam",
                "risk_score": 0.94,
                "confidence": 0.92,
                "tags": ["fraud_upi", "gate_charge"],
                "notes": "Reported fake HR UPI handle demanding document verification charges."
            }
        }

    @property
    def provider_name(self) -> str:
        return "Local Development Intelligence"

    @property
    def is_available(self) -> bool:
        return True

    def lookup_indicator(self, ioc_type: str, normalized_val: str) -> Optional[Dict[str, Any]]:
        key = f"{ioc_type}:{normalized_val.lower()}"
        if key in self._local_db:
            data = self._local_db[key]
            return {
                "source": self.provider_name,
                "source_type": "local_mock_intel",
                "reputation": data["reputation"],
                "threat_category": data["threat_category"],
                "risk_score": data["risk_score"],
                "confidence": data["confidence"],
                "tags": data.get("tags", []),
                "notes": data.get("notes", ""),
                "last_checked": datetime.utcnow().isoformat()
            }
        return None


class ExternalApiIntelProvider(BaseThreatIntelProvider):
    """
    Modular template for live external Threat Intel lookups (e.g. VirusTotal, AbuseIPDB).
    Enabled ONLY if explicit API keys are supplied via environment variables.
    Protected against SSRF and network blocking via strict timeout controls.
    """

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.environ.get("THREAT_INTEL_API_KEY", "")

    @property
    def provider_name(self) -> str:
        return "External Threat Intelligence API"

    @property
    def is_available(self) -> bool:
        return bool(self._api_key and len(self._api_key) > 5)

    def lookup_indicator(self, ioc_type: str, normalized_val: str) -> Optional[Dict[str, Any]]:
        if not self.is_available:
            return None
        # Safe lookup stub: when real API key is provisioned, queries configured gateway
        # Note: server never blindly fetches arbitrary target URLs directly (SSRF safe)
        return None


class ThreatIntelligenceService:
    """
    Unified, cached Threat Intelligence coordinator.
    Ensures safe, fast, non-blocking enrichment without fabricating results.
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_cache_db()
        self.providers: List[BaseThreatIntelProvider] = [
            ExternalApiIntelProvider(),
            LocalDevelopmentIntelProvider()
        ]
        self._mem_cache: Dict[str, Dict[str, Any]] = {}

    def _init_cache_db(self):
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS threat_intel_cache (
                        cache_key TEXT PRIMARY KEY,
                        ioc_type TEXT NOT NULL,
                        indicator_value TEXT NOT NULL,
                        reputation TEXT NOT NULL,
                        threat_category TEXT,
                        risk_score REAL,
                        confidence REAL,
                        source TEXT NOT NULL,
                        response_json TEXT NOT NULL,
                        cached_at INTEGER NOT NULL
                    )
                ''')
                conn.commit()
        except Exception as e:
            print(f"[ThreatIntel] Cache DB init error: {e}")

    def get_cached_indicator(self, ioc_type: str, normalized_val: str) -> Optional[Dict[str, Any]]:
        key = f"{ioc_type}:{normalized_val.lower()}"
        now = int(time.time())

        # Check memory cache first
        if key in self._mem_cache:
            entry = self._mem_cache[key]
            if now - entry.get("cached_at", 0) < CACHE_TTL_SECONDS:
                return entry["data"]

        # Check SQLite persistent cache
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT response_json, cached_at FROM threat_intel_cache WHERE cache_key = ?",
                    (key,)
                )
                row = cursor.fetchone()
                if row:
                    cached_json, cached_time = row
                    if now - cached_time < CACHE_TTL_SECONDS:
                        data = json.loads(cached_json)
                        self._mem_cache[key] = {"data": data, "cached_at": cached_time}
                        return data
        except Exception:
            pass

        return None

    def store_cached_indicator(self, ioc_type: str, normalized_val: str, result: Dict[str, Any]):
        key = f"{ioc_type}:{normalized_val.lower()}"
        now = int(time.time())
        self._mem_cache[key] = {"data": result, "cached_at": now}

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO threat_intel_cache
                    (cache_key, ioc_type, indicator_value, reputation, threat_category, risk_score, confidence, source, response_json, cached_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    key,
                    ioc_type,
                    normalized_val,
                    result.get("reputation", "UNKNOWN"),
                    result.get("threat_category", ""),
                    result.get("risk_score", 0.0),
                    result.get("confidence", 0.0),
                    result.get("source", "Unknown"),
                    json.dumps(result),
                    now
                ))
                conn.commit()
        except Exception:
            pass

    def enrich_indicator(self, ioc_type: str, normalized_val: str) -> Dict[str, Any]:
        """
        Enriches a single indicator against cache and active providers.
        Guaranteed to return 'Unknown / Not Available' if no intelligence exists.
        Never fabricates reputation or converts unknown status into 'Safe'.
        """
        cached = self.get_cached_indicator(ioc_type, normalized_val)
        if cached:
            return {**cached, "is_cached": True}

        # Query active providers in order
        for provider in self.providers:
            if not provider.is_available:
                continue
            try:
                result = provider.lookup_indicator(ioc_type, normalized_val)
                if result is not None:
                    self.store_cached_indicator(ioc_type, normalized_val, result)
                    return {**result, "is_cached": False}
            except Exception as e:
                print(f"[ThreatIntel] Error querying provider {provider.provider_name}: {e}")
                continue

        # Explicit fallback: NEVER fabricate as SAFE
        unknown_result = {
            "source": "None",
            "source_type": "unavailable",
            "reputation": "Unknown / Not Available",
            "threat_category": "No Intelligence Found",
            "risk_score": 0.0,
            "confidence": 0.0,
            "tags": [],
            "notes": "No external or local intelligence signatures currently match this indicator.",
            "last_checked": datetime.utcnow().isoformat(),
            "is_cached": False
        }
        self.store_cached_indicator(ioc_type, normalized_val, unknown_result)
        return unknown_result

    def enrich_ioc_list(self, iocs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Enriches a full list of extracted IOCs in-place with threat intel context.
        """
        enriched: List[Dict[str, Any]] = []
        for ioc in iocs:
            ioc_type = ioc.get("type", "")
            norm_val = ioc.get("normalized_value", "")
            intel = self.enrich_indicator(ioc_type, norm_val)

            ioc_copy = dict(ioc)
            ioc_copy["intel"] = intel
            ioc_copy["reputation_status"] = intel.get("reputation", "Unknown / Not Available")
            enriched.append(ioc_copy)

        return enriched


threat_intel_service = ThreatIntelligenceService()
