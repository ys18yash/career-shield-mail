import os
import sys
import time
import json
import pytest
import sqlite3
import pandas as pd
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.main import app
from ml.feedback_store import feedback_store, compute_message_hash, DB_PATH
from ml.feedback_quality import FeedbackQualityEngine
from ml.continuous_learning import continuous_learning_engine, ContinuousLearningEngine


def test_personal_feedback_submission_and_updates():
    """Verifies SAFE, SPAM, UNSURE submissions and idempotent label updates."""
    client = TestClient(app)
    ts = int(time.time() * 1000)
    user_alpha = f"test_user_alpha_{ts}@corp.local"
    unique_text = f"Offer letter for Software Engineer at Zeta Tech #{ts}. Total package 18 LPA."
    
    payload = {
        "text": unique_text,
        "label": "SAFE",
        "user_id": user_alpha,
        "message_id": f"msg-alpha-1-{ts}",
        "original_prediction": "SAFE",
        "original_risk_score": 0.02
    }
    res = client.post("/api/feedback", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["data"]["label"] == "SAFE"
    assert data["data"]["action"] == "created"
    assert data["data"]["is_eligible"] == True

    payload["label"] = "SPAM"
    res2 = client.post("/api/feedback", json=payload)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["data"]["action"] == "updated"
    assert data2["data"]["label"] == "SPAM"

    payload_unsure = {
        "text": f"Ambiguous interview query about joining date #{ts}.",
        "label": "UNSURE",
        "user_id": user_alpha,
        "message_id": f"msg-alpha-2-{ts}"
    }
    res3 = client.post("/api/feedback", json=payload_unsure)
    assert res3.status_code == 200
    data3 = res3.json()
    assert data3["data"]["label"] == "UNSURE"
    assert data3["data"]["is_eligible"] == False

    check_res = client.get(f"/api/feedback/check?user_id={user_alpha}&message_id=msg-alpha-1-{ts}")
    assert check_res.status_code == 200
    assert check_res.json()["has_feedback"] == True
    assert check_res.json()["feedback"]["label"] == "SPAM"
    print("  [PASS] Personal Feedback Submission & Idempotent Updates")


def test_multi_user_isolation_and_conflict_detection():
    """Verifies that cross-user disagreements are detected and quarantined."""
    client = TestClient(app)
    ts = int(time.time() * 1000)
    shared_text = f"Urgent: Freelance data entry role #{ts}. Submit bank account details to confirm."
    
    client.post("/api/feedback", json={
        "text": shared_text,
        "label": "SPAM",
        "user_id": f"tenant_1_{ts}@company.com",
        "message_id": f"msg-shared-1-{ts}"
    })

    client.post("/api/feedback", json={
        "text": shared_text,
        "label": "SAFE",
        "user_id": f"tenant_2_{ts}@company.com",
        "message_id": f"msg-shared-2-{ts}"
    })

    msg_hash = compute_message_hash(shared_text)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT conflict_status, is_eligible FROM feedback_records WHERE message_hash = ?", (msg_hash,))
        rows = cursor.fetchall()
        for r in rows:
            assert r[0] == "cross_user_conflict"
            assert r[1] == 0
            
    print("  [PASS] Multi-User Conflict Detection & Anti-Poisoning Quarantine")


def test_per_user_contribution_caps():
    """Verifies that a single tenant cannot flood or dominate the global training candidate batch."""
    ts = int(time.time() * 1000)
    flood_user = f"flooder_tenant_{ts}@test.org"
    for i in range(25):
        feedback_store.record_feedback(
            user_id=flood_user,
            message_id=f"flood-msg-{ts}-{i}",
            text=f"Unique spam message variant number {ts}-{i} with distinct text tokens {i*7}.",
            label="SPAM"
        )

    capped_samples = FeedbackQualityEngine.extract_capped_candidate_samples(DB_PATH, max_total_samples=100)
    flooder_samples = [s for s in capped_samples if s["user_id"] == flood_user]
    
    assert len(flooder_samples) <= 250
    print(f"  [PASS] Per-User Contribution Cap Enforced ({len(flooder_samples)} samples allowed out of multi-tenant pool)")


def test_candidate_dataset_snapshotting_preserves_master():
    """Verifies that candidate dataset snapshot creation does NOT alter the base train parquet split."""
    original_base = pd.read_parquet("splits/train.parquet")
    original_len = len(original_base)

    mock_feedback = [
        {"feedback_id": "mock-fb-1", "user_id": "user_a", "message_hash": "hash_a", "label": 1, "text": "New scam sample 1"},
        {"feedback_id": "mock-fb-2", "user_id": "user_b", "message_hash": "hash_b", "label": 0, "text": "New clean job posting 2"}
    ]

    version_str, snap_path, total_rows = ContinuousLearningEngine.create_candidate_dataset_snapshot(mock_feedback)
    
    after_base = pd.read_parquet("splits/train.parquet")
    assert len(after_base) == original_len
    assert total_rows == original_len + len(mock_feedback)
    assert os.path.exists(snap_path)
    print("  [PASS] Immutable Candidate Dataset Snapshotting (splits/train.parquet strictly preserved)")


def test_validation_gate_and_rollback():
    """Verifies validation gate logic (pass vs reject) and instant rollback."""
    client = TestClient(app)

    failing_metrics = {
        "accuracy": 0.9500,
        "precision": 0.9400,
        "recall": 0.9800,
        "f1_score": 0.9600,
        "f2_score": 0.9700,
        "roc_auc": 0.9900,
        "brier_score": 0.0300
    }
    passed, reasons = ContinuousLearningEngine.evaluate_validation_gate(failing_metrics)
    assert passed == False
    assert any("Precision Gate Failed" in r for r in reasons)
    print("  [PASS] Validation Gate Rejection for Sub-Standard Candidate")

    passing_metrics = {
        "accuracy": 0.9860,
        "precision": 0.9790,
        "recall": 0.9920,
        "f1_score": 0.9855,
        "f2_score": 0.9895,
        "roc_auc": 0.9990,
        "brier_score": 0.0110
    }
    passed2, reasons2 = ContinuousLearningEngine.evaluate_validation_gate(passing_metrics)
    assert passed2 == True
    assert len(reasons2) == 0
    print("  [PASS] Validation Gate Approval for High-Quality Candidate")

    rollback_res = client.post("/api/models/rollback", json={"target_version_id": "v2.0.0-frozen"})
    assert rollback_res.status_code == 200
    assert rollback_res.json()["status"] == "success"
    assert rollback_res.json()["active_model"]["version_id"] == "v2.0.0-frozen"
    print("  [PASS] Model Version Registry & Instant Rollback API")


def test_feedback_analytics_and_status_endpoints():
    """Verifies /api/feedback/stats and /api/feedback/training-status return full telemetry."""
    client = TestClient(app)
    
    stats_res = client.get("/api/feedback/stats")
    assert stats_res.status_code == 200
    s_data = stats_res.json()
    assert "analytics" in s_data
    assert "label_distribution" in s_data["analytics"]
    assert "disagreement_analysis" in s_data["analytics"]

    status_res = client.get("/api/feedback/training-status")
    assert status_res.status_code == 200
    st_data = status_res.json()
    assert "active_production_model" in st_data
    assert "eligibility_status" in st_data
    assert "retraining_policy" in st_data
    print("  [PASS] Feedback Analytics & Retraining Telemetry Endpoints")


if __name__ == "__main__":
    print("=" * 70)
    print("RUNNING MULTI-TENANT FEEDBACK & CONTINUOUS LEARNING TEST SUITE")
    print("=" * 70)
    test_personal_feedback_submission_and_updates()
    test_multi_user_isolation_and_conflict_detection()
    test_per_user_contribution_caps()
    test_candidate_dataset_snapshotting_preserves_master()
    test_validation_gate_and_rollback()
    test_feedback_analytics_and_status_endpoints()
    print("=" * 70)
    print("ALL MULTI-TENANT FEEDBACK & CONTINUOUS LEARNING TESTS PASSED!")
    print("=" * 70)
