import pytest
from fastapi.testclient import TestClient
from api.main import app
from ml.ioc_extractor import IOCExtractor, defang_indicator
from ml.threat_intel import ThreatIntelligenceService
from ml.risk_correlator import SecurityRiskCorrelator
from ml.security_alerts import SecurityAlertManager

client = TestClient(app)

# ==========================================
# 1. IOC EXTRACTION & DEFANGING TESTS
# ==========================================

class TestIOCExtraction:
    def test_extract_urls_and_domains(self):
        text = "Please verify your application at https://scam-careers-portal.xyz/apply or visit bit.ly/urgent-job"
        iocs = IOCExtractor.extract_all_iocs(text)
        types = [i["type"] for i in iocs]
        
        assert "url" in types
        assert "domain" in types
        
        # Check defanging
        url_ioc = next(i for i in iocs if i["type"] == "url" and "scam-careers" in i["value"])
        assert "hxxps://" in url_ioc["defanged_value"] or "[.]" in url_ioc["defanged_value"]

    def test_extract_ipv4_and_ipv6(self):
        text = "Server routed via 192.168.1.100 and external host 185.220.101.5 and 2001:0db8:85a3:0000:0000:8a2e:0370:7334"
        iocs = IOCExtractor.extract_all_iocs(text)
        
        ipv4_iocs = [i for i in iocs if i["type"] == "ipv4"]
        ipv6_iocs = [i for i in iocs if i["type"] == "ipv6"]
        
        assert len(ipv4_iocs) >= 2
        assert len(ipv6_iocs) >= 1
        
        # Check defanging of IPv4
        assert any("[.]" in i["defanged_value"] for i in ipv4_iocs)

    def test_extract_payment_handles(self):
        text = "Transfer registration fee of 999 INR to hr-amazon@upi or paymentdesk@okaxis immediately."
        iocs = IOCExtractor.extract_all_iocs(text)
        
        payment_iocs = [i for i in iocs if i["type"] == "payment_handle"]
        assert len(payment_iocs) >= 1
        assert any("hr-amazon" in i["value"] for i in payment_iocs)
        assert any("[at]" in i["defanged_value"] for i in payment_iocs)

    def test_extract_crypto_hashes(self):
        sha256_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        md5_hash = "d41d8cd98f00b204e9800998ecf8427e"
        text = f"Attachment Hash SHA-256: {sha256_hash} and MD5: {md5_hash}"
        
        iocs = IOCExtractor.extract_all_iocs(text)
        hashes = [i for i in iocs if i["type"] == "file_hash"]
        
        assert len(hashes) >= 2
        assert any(i["value"] == sha256_hash for i in hashes)
        assert any(i["value"] == md5_hash for i in hashes)

    def test_extract_attachments(self):
        text = "Find attached Appointment_Letter_Final.pdf and Verification_Form.exe for signing."
        iocs = IOCExtractor.extract_all_iocs(text)
        
        attachments = [i for i in iocs if i["type"] == "attachment"]
        assert len(attachments) >= 2
        assert any("Appointment_Letter_Final.pdf" in i["value"] for i in attachments)
        assert any("Verification_Form.exe" in i["value"] for i in attachments)

    def test_deduplication_and_confidence(self):
        text = "Visit https://scam-domain.com/apply and check https://scam-domain.com/apply again."
        iocs = IOCExtractor.extract_all_iocs(text)
        
        urls = [i for i in iocs if i["type"] == "url" and "scam-domain.com" in i["value"]]
        assert len(urls) == 1
        assert 0.0 <= urls[0]["confidence"] <= 1.0


# ==========================================
# 2. THREAT INTEL PROVIDER & CACHE TESTS
# ==========================================

class TestThreatIntelligence:
    def setup_method(self):
        self.service = ThreatIntelligenceService()

    def test_local_signatures_lookup(self):
        intel = self.service.enrich_indicator("payment_handle", "hr-amazon@upi")
        
        assert intel["reputation"] == "MALICIOUS"
        assert intel.get("threat_category") is not None
        assert "Local Development Intelligence" in (intel.get("source") or "")

    def test_unknown_indicators_not_fabricated(self):
        # Strict requirement: Never fabricate intelligence, must return 'Unknown / Not Available'
        intel = self.service.enrich_indicator("domain", "completely-random-unseen-domain-987654.org")
        
        assert intel["reputation"] == "Unknown / Not Available"
        assert intel["risk_score"] == 0.0

    def test_enrich_ioc_list(self):
        iocs = [
            {"type": "domain", "value": "skillinfytech-careers.online", "normalized_value": "skillinfytech-careers.online"},
            {"type": "domain", "value": "unknown-foo-bar-123.com", "normalized_value": "unknown-foo-bar-123.com"}
        ]
        enriched = self.service.enrich_ioc_list(iocs)
        
        assert len(enriched) == 2
        assert enriched[0]["reputation_status"] == "MALICIOUS"
        assert enriched[1]["reputation_status"] == "Unknown / Not Available"


# ==========================================
# 3. RISK CORRELATION ENGINE TESTS
# ==========================================

class TestRiskCorrelation:
    def test_deterministic_weighted_scoring(self):
        ml_score = 0.90
        enriched_iocs = [
            {"type": "domain", "value": "scam.xyz", "normalized_value": "scam.xyz", "reputation_status": "MALICIOUS", "intel": {"reputation": "MALICIOUS", "threat_category": "Phishing"}}
        ]
        security_triggers = [
            {"category": "Micro-Fee / Upfront Charge Scam", "severity": "HIGH", "detail": "Monetary fee requested"}
        ]
        
        res = SecurityRiskCorrelator.correlate(
            ml_risk_score=ml_score,
            security_triggers=security_triggers,
            enriched_iocs=enriched_iocs,
            sender_email="recruiter@protonmail.com",
            subject="Job Opportunity"
        )
        
        assert 0.0 <= res["overall_risk_score"] <= 1.0
        assert res["overall_risk_score"] >= 0.70
        assert res["severity"] in ["HIGH", "CRITICAL"]
        assert "ml_risk" in res["sub_scores"]
        assert "ioc_risk" in res["sub_scores"]
        assert "sender_risk" in res["sub_scores"]
        assert "link_risk" in res["sub_scores"]
        assert "content_risk" in res["sub_scores"]

    def test_malicious_ioc_escalation_rule(self):
        # Even if ML model was uncertain (0.30), a confirmed malicious IOC must escalate risk to CRITICAL
        enriched_iocs = [
            {"type": "payment_handle", "value": "hr-amazon@upi", "normalized_value": "hr-amazon@upi", "reputation_status": "MALICIOUS", "intel": {"reputation": "MALICIOUS", "threat_category": "Payment Fraud"}}
        ]
        
        res = SecurityRiskCorrelator.correlate(
            ml_risk_score=0.30,
            security_triggers=[],
            enriched_iocs=enriched_iocs,
            sender_email="legit-looking@gmail.com"
        )
        
        assert res["overall_risk_score"] >= 0.85
        assert res["severity"] == "CRITICAL"

    def test_benign_corporate_email_scoring(self):
        res = SecurityRiskCorrelator.correlate(
            ml_risk_score=0.02,
            security_triggers=[],
            enriched_iocs=[],
            sender_email="recruiter@google.com",
            subject="Technical Interview Schedule"
        )
        
        assert res["overall_risk_score"] <= 0.20
        assert res["severity"] == "LOW"


# ==========================================
# 4. SECURITY ALERTS & AUDIT TIMELINE TESTS
# ==========================================

class TestSecurityAlertManager:
    def setup_method(self):
        self.manager = SecurityAlertManager()

    def test_alert_lifecycle_and_timeline(self):
        message_id = f"test-mail-{abs(hash('mail1')) % 100000}"
        
        # 1. Create Alert
        alert = self.manager.create_or_update_alert(
            user_id="default_user",
            message_id=message_id,
            subject="Earn 5000 Daily Rating Hotels",
            sender="scammer@outlook.com",
            severity="CRITICAL",
            threat_type="Task Scam",
            overall_risk_score=0.92,
            threat_probability=0.95,
            iocs=[{"type": "domain", "value": "task-earn.xyz", "reputation_status": "MALICIOUS"}],
            risk_breakdown={"ml_sub_score": 0.95, "reasons": ["Task fraud"]},
            ml_analysis={"is_spam": True, "risk_score": 0.95}
        )
        alert_id = alert["alert_id"]
        assert alert["status"] == "OPEN"
        
        # 2. Transition Status to INVESTIGATING
        updated = self.manager.update_alert_status(
            alert_id=alert_id,
            status="INVESTIGATING",
            assigned_to="analyst@sec.corp",
            resolution_notes="Analyst started investigation"
        )
        assert updated["status"] == "INVESTIGATING"
        
        # 3. Transition Status to RESOLVED
        resolved = self.manager.update_alert_status(
            alert_id=alert_id,
            status="RESOLVED",
            assigned_to="analyst@sec.corp",
            resolution_notes="Domain blocklisted and user notified"
        )
        assert resolved["status"] == "RESOLVED"
        
        # 4. Check Timeline Audit Events
        full_alert = self.manager.get_alert_by_id(alert_id)
        timeline = full_alert.get("timeline", [])
        event_types = [e["event_type"] for e in timeline]
        
        assert "ALERT_CREATED" in event_types
        assert "ALERT_UPDATED" in event_types
        assert "INCIDENT_RESOLVED" in event_types

    def test_tenant_isolation(self):
        m1 = f"t1-mail-{abs(hash('m1')) % 100000}"
        m2 = f"t2-mail-{abs(hash('m2')) % 100000}"
        
        a1 = self.manager.create_or_update_alert(
            user_id="tenant_alpha",
            message_id=m1,
            subject="Tenant 1 Alert",
            sender="attacker@t1.com",
            severity="HIGH",
            threat_type="Phishing",
            overall_risk_score=0.88,
            threat_probability=0.90,
            iocs=[],
            risk_breakdown={},
            ml_analysis={}
        )
        
        a2 = self.manager.create_or_update_alert(
            user_id="tenant_beta",
            message_id=m2,
            subject="Tenant 2 Alert",
            sender="attacker@t2.com",
            severity="HIGH",
            threat_type="Phishing",
            overall_risk_score=0.88,
            threat_probability=0.90,
            iocs=[],
            risk_breakdown={},
            ml_analysis={}
        )
        
        alerts_t1 = self.manager.list_alerts(user_id="tenant_alpha")
        alerts_t2 = self.manager.list_alerts(user_id="tenant_beta")
        
        t1_ids = [a["alert_id"] for a in alerts_t1]
        t2_ids = [a["alert_id"] for a in alerts_t2]
        
        assert a1["alert_id"] in t1_ids
        assert a2["alert_id"] not in t1_ids
        assert a2["alert_id"] in t2_ids
        assert a1["alert_id"] not in t2_ids


# ==========================================
# 5. FASTAPI SECURITY ENDPOINTS TESTS
# ==========================================

class TestSecurityAPIEndpoints:
    def test_security_analyze_endpoint(self):
        payload = {
            "text": "Congratulations! You have been selected without interview. Transfer 999 INR deposit to hr-amazon@upi.",
            "subject": "Direct Appointment: Amazon India Product Reviewer",
            "sender": "amazon-jobs-desk@gmail.com",
            "model": "Stacking Ensemble"
        }
        
        response = client.post("/api/security/analyze", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "risk_correlation" in data
        assert "alert" in data
        assert data["alert"] is not None
        assert data["alert"]["alert_id"].startswith("ALERT-")
        assert "iocs" in data["alert"] or "extracted_iocs" in data

    def test_security_alerts_list_and_filter(self):
        response = client.get("/api/security/alerts?limit=10")
        assert response.status_code == 200
        
        data = response.json()
        assert "alerts" in data
        assert "count" in data

    def test_ioc_lookup_endpoint(self):
        response = client.get("/api/security/iocs/lookup?ioc_type=payment_handle&value=hr-amazon@upi")
        assert response.status_code == 200
        
        data = response.json()
        assert data["value"] == "hr-amazon@upi"
        assert data["intel"]["reputation"] == "MALICIOUS"
        assert data["defanged_value"] == "hr-amazon[at]upi"

    def test_security_stats_endpoint(self):
        response = client.get("/api/security/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert "total_alerts" in data
        assert "open_alerts" in data

    def test_alert_triage_and_feedback_flow(self):
        # 1. Create via analyze
        analyze_res = client.post("/api/security/analyze", json={
            "text": "Pay 1500 INR processing fee to confirm Assistant Manager role.",
            "subject": "Fake Job Reviewer Offer",
            "sender": "scam@protonmail.com"
        })
        assert analyze_res.status_code == 200
        alert_id = analyze_res.json()["alert"]["alert_id"]
        
        # 2. Patch status
        patch_res = client.patch(f"/api/security/alerts/{alert_id}", json={
            "status": "INVESTIGATING",
            "resolution_notes": "Triage in progress",
            "assigned_to": "analyst@test.corp"
        })
        assert patch_res.status_code == 200
        assert patch_res.json()["alert"]["status"] == "INVESTIGATING"
        
        # 3. Submit analyst feedback
        fb_res = client.post(f"/api/security/alerts/{alert_id}/feedback", json={
            "label": "SPAM",
            "notes": "Confirmed upfront fee phishing",
            "user_id": "analyst@test.corp"
        })
        assert fb_res.status_code == 200
        assert fb_res.json()["status"] == "success"
        
        # 4. Fetch timeline
        tl_res = client.get(f"/api/security/alerts/{alert_id}/timeline")
        assert tl_res.status_code == 200
        tl_events = [e["event_type"] for e in tl_res.json()["timeline"]]
        assert "FEEDBACK_SUBMITTED" in tl_events
