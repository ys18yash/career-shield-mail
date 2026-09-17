import os
import sys
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.main import app
from ml.gmail_sync import GmailClient

def test_mock_gmail_sync():
    client = TestClient(app)

    # 1. Connect with mock credentials
    payload = {
        "email": "mock@example.com",
        "app_password": "mockpassword1234"
    }
    res = client.post("/api/gmail/connect", json=payload)
    assert res.status_code == 200
    assert res.json()["status"] == "connected"
    print("  [PASS] Mock Gmail Connect")

    # 2. Status
    res_status = client.get("/api/gmail/status")
    assert res_status.status_code == 200
    assert res_status.json()["is_connected"] == True
    print("  [PASS] Gmail Status Endpoint")

    # 3. Fetch
    res_fetch = client.get("/api/gmail/fetch")
    assert res_fetch.status_code == 200
    data = res_fetch.json()
    assert "inbox" in data and "spam" in data
    assert len(data["all"]) > 0
    print(f"  [PASS] Mock Gmail Fetch & Classification ({data['inbox_count']} inbox, {data['spam_count']} spam)")

    # 4. Disconnect
    res_disc = client.post("/api/gmail/disconnect")
    assert res_disc.status_code == 200
    assert res_disc.json()["status"] == "disconnected"
    print("  [PASS] Gmail Disconnect Endpoint")

if __name__ == "__main__":
    print("RUNNING GMAIL INTEGRATION TESTS")
    test_mock_gmail_sync()
    print("ALL GMAIL INTEGRATION TESTS PASSED.")
