import os
import sys
import time
import json
import psutil
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml.explain import ModelExplainer
from api.main import app

def measure_system_performance():
    print("=" * 80)
    print("CAREERSHIELD MAIL: EMPIRICAL PERFORMANCE & LATENCY PROFILING")
    print("=" * 80)

    process = psutil.Process(os.getpid())
    mem_before = process.memory_info().rss / (1024 * 1024)

    t0_load = time.time()
    explainer = ModelExplainer()
    load_time_sec = time.time() - t0_load
    mem_after = process.memory_info().rss / (1024 * 1024)

    print(f"  -> Model Suite & Vectorizer Loading Time : {load_time_sec * 1000:.2f} ms")
    print(f"  -> Process Memory Allocation (RSS)       : {mem_after:.2f} MB (Delta: +{mem_after - mem_before:.2f} MB)")

    sample_email = (
        "SkillInfyTech 4-Weeks Internship Program. No internship fee. "
        "Access Fee: ₹89 only for Digital ID Card & platform access. "
        "Payment via UPI or GPay to verify your candidate slot."
    )

    t0_feat = time.time()
    for _ in range(100):
        _ = explainer.transform_text(sample_email)
    feat_time_ms = ((time.time() - t0_feat) / 100.0) * 1000.0
    print(f"  -> Average Feature Extraction Latency   : {feat_time_ms:.3f} ms / email")

    models = [
        "Naive Bayes", "Logistic Regression", "Support Vector Machine",
        "Random Forest", "Extra Trees Ensemble", "XGBoost",
        "Deep Neural Net (MLP)", "Stacking Ensemble"
    ]
    
    print("\n--- MODEL INFERENCE LATENCY (100 Iterations Each) ---")
    latency_results = {}
    for m in models:
        t0_inf = time.time()
        for _ in range(100):
            _ = explainer.explain(sample_email, model_name=m)
        lat_ms = ((time.time() - t0_inf) / 100.0) * 1000.0
        latency_results[m] = round(lat_ms, 3)
        print(f"  {m:<26} : {lat_ms:6.3f} ms / email")

    client = TestClient(app)
    t0_api = time.time()
    for _ in range(50):
        _ = client.post("/api/predict", json={"text": sample_email, "model": "Stacking Ensemble"})
    api_lat_ms = ((time.time() - t0_api) / 50.0) * 1000.0
    print(f"\n  -> FastAPI Roundtrip Latency (/api/predict): {api_lat_ms:.3f} ms")

    performance_summary = {
        "model_loading_ms": round(load_time_sec * 1000, 2),
        "memory_rss_mb": round(mem_after, 2),
        "feature_extraction_ms": round(feat_time_ms, 3),
        "model_latencies_ms": latency_results,
        "fastapi_roundtrip_ms": round(api_lat_ms, 3),
        "throughput_emails_per_sec": round(1000.0 / max(api_lat_ms, 0.001), 1)
    }

    os.makedirs("reports", exist_ok=True)
    with open("reports/system_performance.json", "w", encoding="utf-8") as f:
        json.dump(performance_summary, f, indent=2)
    print("  -> Saved reports/system_performance.json")
    print("=" * 80)

if __name__ == "__main__":
    measure_system_performance()
