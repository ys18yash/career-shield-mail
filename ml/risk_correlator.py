"""
CareerShield Mail - Transparent Security Risk Correlation Layer.

Combines ML threat probability, 22 handcrafted security heuristics,
enriched IOC reputations, and identity signals into a deterministic,
fully explainable multi-vector security assessment.

Scoring Methodology:
- Deterministic weighted correlation model across 5 vectors:
  1. ML Model Threat Probability (weight: 0.35)
  2. IOC Threat Intelligence & Reputations (weight: 0.25)
  3. Sender & Identity Verification (weight: 0.15)
  4. Link & Embedded URL Risks (weight: 0.15)
  5. Content & Psychological Deception Signals (weight: 0.10)
- Escalation Rules: Hard critical triggers (e.g. active MALICIOUS threat intel,
  advance micro-fee traps, or confirmed P2P fraud handles) enforce minimum
  CRITICAL or HIGH severity overrides.
"""

from typing import Dict, Any, List, Optional
import numpy as np


class SecurityRiskCorrelator:
    """
    Transparent multi-vector risk correlation and triage scoring engine.
    Produces granular sub-scores, overall severity rating, and explainable key risk factors.
    """

    @classmethod
    def correlate(
        cls,
        ml_risk_score: float,
        security_triggers: List[Dict[str, Any]],
        enriched_iocs: List[Dict[str, Any]],
        linguistic_metrics: Optional[Dict[str, Any]] = None,
        sender_email: Optional[str] = None,
        sender_display: Optional[str] = None,
        subject: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes full deterministic risk correlation across all available intelligence streams.
        """
        ml_score = float(np.clip(ml_risk_score, 0.0, 1.0))
        risk_factors: List[Dict[str, str]] = []

        # 1. Evaluate IOC Threat Intelligence Risk (0.0 to 1.0)
        ioc_score = 0.0
        malicious_iocs = []
        suspicious_iocs = []
        benign_iocs = []

        for ioc in enriched_iocs:
            intel = ioc.get("intel", {})
            rep = (intel.get("reputation") or ioc.get("reputation_status") or "").upper()
            ioc_val = ioc.get("defanged_value") or ioc.get("normalized_value") or ioc.get("value")

            if "MALICIOUS" in rep:
                ioc_score = max(ioc_score, 0.95)
                malicious_iocs.append(f"{ioc.get('type')}: {ioc_val} ({intel.get('threat_category', 'Malicious Signature')})")
            elif "SUSPICIOUS" in rep:
                ioc_score = max(ioc_score, 0.70)
                suspicious_iocs.append(f"{ioc.get('type')}: {ioc_val}")
            elif "BENIGN" in rep:
                benign_iocs.append(ioc_val)

        if malicious_iocs:
            risk_factors.append({
                "vector": "Threat Intelligence",
                "severity": "CRITICAL",
                "description": f"Enriched IOC matched known malicious threat intelligence: {'; '.join(malicious_iocs[:2])}"
            })
        elif suspicious_iocs:
            risk_factors.append({
                "vector": "Threat Intelligence",
                "severity": "HIGH",
                "description": f"Enriched IOC matched suspicious telemetry: {'; '.join(suspicious_iocs[:2])}"
            })

        # 2. Evaluate Sender & Identity Risk (0.0 to 1.0)
        sender_score = 0.0
        has_free_email_flag = any(t.get("category") == "Domain Spoofing" for t in security_triggers)
        has_brand_impersonation = any(t.get("category") == "Brand Impersonation" for t in security_triggers)

        if has_brand_impersonation and has_free_email_flag:
            sender_score = 0.90
            risk_factors.append({
                "vector": "Sender Identity",
                "severity": "CRITICAL",
                "description": "High-risk brand impersonation: Corporate brand claimed from a free public webmail address."
            })
        elif has_free_email_flag:
            sender_score = 0.60
            risk_factors.append({
                "vector": "Sender Identity",
                "severity": "HIGH",
                "description": "Professional offer dispatched from unverified free email service provider."
            })
        elif any(t.get("category") == "Corporate Domain" for t in security_triggers):
            sender_score = 0.05

        # 3. Evaluate Link & URL Risk (0.0 to 1.0)
        link_score = 0.0
        has_suspicious_link = any(t.get("category") == "Suspicious Links" for t in security_triggers)
        suspicious_tld_iocs = [
            ioc for ioc in enriched_iocs 
            if ioc.get("type") in ("url", "domain") and ioc.get("metadata", {}).get("is_suspicious_tld")
        ]

        if suspicious_tld_iocs:
            link_score = max(link_score, 0.85)
            risk_factors.append({
                "vector": "Link Safety",
                "severity": "HIGH",
                "description": "Embedded hyperlinks utilize high-risk top-level domain (TLD) associated with phishing campaigns."
            })
        elif has_suspicious_link:
            link_score = max(link_score, 0.75)
            risk_factors.append({
                "vector": "Link Safety",
                "severity": "HIGH",
                "description": "Contains URL shorteners or deceptive tracking redirection links."
            })
        elif any(t.get("category") == "Verified ATS Portal" for t in security_triggers):
            link_score = 0.02

        # 4. Evaluate Content & Psychological Deception Risk (0.0 to 1.0)
        content_score = 0.0
        has_micro_fee = any(t.get("category") == "Micro-Fee / ID Card Scam Trap" for t in security_triggers)
        has_financial = any(t.get("category") == "Financial Advance Fee / Charge" for t in security_triggers)
        has_urgency = any(t.get("category") == "Psychological Urgency & Scarcity" for t in security_triggers)
        has_regulatory = any(t.get("category") == "Regulatory Impersonation (MCA/MSME/AICTE)" for t in security_triggers)

        if has_micro_fee:
            content_score = max(content_score, 0.95)
            risk_factors.append({
                "vector": "Content Deception",
                "severity": "CRITICAL",
                "description": "Deceptive micro-fee scheme detected: Demands upfront digital ID, portal access, or onboarding charge."
            })
        elif has_financial:
            content_score = max(content_score, 0.85)
            risk_factors.append({
                "vector": "Content Deception",
                "severity": "CRITICAL",
                "description": "Explicit demand for advance security deposit, registration fee, or P2P funds transfer."
            })

        if has_regulatory:
            content_score = max(content_score, 0.70)
            risk_factors.append({
                "vector": "Content Deception",
                "severity": "HIGH",
                "description": "Unverified government/regulatory claims (MCA, MSME, AICTE, ISO) used to establish false trust."
            })

        if has_urgency:
            content_score = max(content_score, 0.50)
            risk_factors.append({
                "vector": "Content Deception",
                "severity": "MEDIUM",
                "description": "Psychological pressure tactics detected (artificial deadlines, immediate response demands)."
            })

        # 5. Composite Risk Calculation (Weighted Model)
        # Weights: ML=0.35, IOC=0.25, Sender=0.15, Link=0.15, Content=0.10
        weights = {
            "ml": 0.35,
            "ioc": 0.25,
            "sender": 0.15,
            "link": 0.15,
            "content": 0.10
        }

        weighted_risk = (
            weights["ml"] * ml_score +
            weights["ioc"] * ioc_score +
            weights["sender"] * sender_score +
            weights["link"] * link_score +
            weights["content"] * content_score
        )

        # Hard Escalation Rules
        # - Any confirmed MALICIOUS IOC or Micro-Fee trap guarantees >= 0.85 (CRITICAL)
        # - ML Score >= 0.90 guarantees >= 0.80 (CRITICAL)
        # - Confirmed brand spoofing + free email guarantees >= 0.75 (HIGH)
        if ioc_score >= 0.90 or has_micro_fee:
            overall_risk = max(weighted_risk, 0.88)
        elif ml_score >= 0.90:
            overall_risk = max(weighted_risk, 0.82)
        elif has_brand_impersonation and has_free_email_flag:
            overall_risk = max(weighted_risk, 0.75)
        elif ml_score >= 0.50 or has_financial or has_suspicious_link:
            overall_risk = max(weighted_risk, 0.55)
        elif not risk_factors and ml_score < 0.20:
            overall_risk = min(weighted_risk, 0.10)
        else:
            overall_risk = weighted_risk

        overall_risk = float(np.clip(overall_risk, 0.0, 1.0))

        # Severity Classification
        if overall_risk >= 0.80:
            severity = "CRITICAL"
        elif overall_risk >= 0.50:
            severity = "HIGH"
        elif overall_risk >= 0.20:
            severity = "MEDIUM"
        else:
            severity = "LOW"

        # Determine Primary Threat Category
        if has_micro_fee or "Micro-Fee" in str(malicious_iocs):
            primary_threat_type = "Recruitment Micro-Fee Trap"
        elif has_brand_impersonation:
            primary_threat_type = "Brand Impersonation & Spoofing"
        elif has_financial:
            primary_threat_type = "Advance-Fee Financial Scam"
        elif has_suspicious_link:
            primary_threat_type = "Credential Harvesting & Phishing Link"
        elif any(t.get("category") == "Commercial Bootcamp / Course Marketing Spam" for t in security_triggers):
            primary_threat_type = "Commercial Course Upselling Spam"
        elif ml_score >= 0.50:
            primary_threat_type = "Suspicious Unsolicited Recruitment Scam"
        else:
            primary_threat_type = "Verified Authentic Communication"

        return {
            "overall_risk_score": round(overall_risk, 4),
            "severity": severity,
            "primary_threat_type": primary_threat_type,
            "sub_scores": {
                "ml_risk": round(ml_score, 4),
                "ioc_risk": round(ioc_score, 4),
                "sender_risk": round(sender_score, 4),
                "link_risk": round(link_score, 4),
                "content_risk": round(content_score, 4)
            },
            "scoring_weights": weights,
            "risk_factors": risk_factors,
            "methodology": "Deterministic Multi-Vector Weighted Heuristic Correlation with Hard Escalation Triggers"
        }
