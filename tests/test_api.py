import os
import sys
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.main import app

def test_api_routes():
    client = TestClient(app)

    # 1. Health
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"
    print("  [PASS] /api/health")

    # 2. Ready
    res = client.get("/api/ready")
    assert res.status_code == 200
    assert res.json()["status"] == "ready"
    print("  [PASS] /api/ready")

    # 3. Models
    res = client.get("/api/models")
    assert res.status_code == 200
    assert len(res.json()["models"]) >= 8
    print("  [PASS] /api/models")

    # 4. Predict
    payload = {
        "text": "Selected for 4-week Python internship. Access fee ₹89 via GooglePay.",
        "model": "Stacking Ensemble"
    }
    res = client.post("/api/predict", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["is_spam"] == True
    assert data["risk_score"] > 0.50
    assert "scan_id" in data
    print("  [PASS] /api/predict (Threat detection)")

    # 5. Feed
    res = client.get("/api/feed")
    assert res.status_code == 200
    assert "inbox" in res.json()
    print("  [PASS] /api/feed")

    # 6. Threshold simulate
    res = client.post("/api/simulate-threshold", json={"threshold": 0.05, "model": "Stacking Ensemble"})
    assert res.status_code == 200
    assert "metrics" in res.json()
    print("  [PASS] /api/simulate-threshold")

if __name__ == "__main__":
    print("RUNNING FASTAPI ENDPOINT TESTS")
    test_api_routes()
    print("ALL API ENDPOINT TESTS PASSED.")
