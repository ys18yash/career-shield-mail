import os
import sys
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.main import app

def test_full_system_flow():
    client = TestClient(app)

    r_h = client.get("/api/health")
    assert r_h.status_code == 200
    r_r = client.get("/api/ready")
    assert r_r.status_code == 200

    r_sim = client.post("/api/simulate-incoming")
    assert r_sim.status_code == 200
    sim_mail = r_sim.json()
    assert "ml_analysis" in sim_mail

    legit_payload = {
        "text": "Dear Candidate, We are pleased to offer you the SWE Internship at Google Bangalore. Monthly stipend INR 1,15,000. Review on careers.google.com.",
        "model": "Stacking Ensemble"
    }
    r_legit = client.post("/api/predict", json=legit_payload)
    assert r_legit.status_code == 200
    assert r_legit.json()["is_spam"] == False
    assert r_legit.json()["threat_level"] in ["LOW RISK", "VERIFIED SAFE"]

    scam_payload = {
        "text": "SkillInfyTech 4-Weeks Internship Program. No fee. Access Fee: ₹89 only for Digital ID Card. Pay via UPI immediately.",
        "model": "Stacking Ensemble"
    }
    r_scam = client.post("/api/predict", json=scam_payload)
    assert r_scam.status_code == 200
    assert r_scam.json()["is_spam"] == True
    assert r_scam.json()["threat_level"] in ["CRITICAL THREAT", "SUSPICIOUS PHISHING"]

    r_thresh = client.post("/api/simulate-threshold", json={"threshold": 0.05, "model": "Stacking Ensemble"})
    assert r_thresh.status_code == 200
    assert "metrics" in r_thresh.json()

    print("  [PASS] Full End-to-End System Integration Flow")

if __name__ == "__main__":
    print("RUNNING END-TO-END SYSTEM TESTS")
    test_full_system_flow()
    print("ALL END-TO-END TESTS PASSED.")
