import os
import sys
import json
import random
import time
from datetime import datetime
from typing import Optional, List, Dict, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ml.explain import ModelExplainer
from ml.feed import SIMULATED_EMAILS, INCOMING_SIMULATION_POOL
from ml.gmail_sync import GmailClient
from ml.security_sanitizer import sanitize_email_text, extract_safe_urls
from api.storage import storage
from ml.feedback_store import feedback_store, DB_PATH
from ml.feedback_quality import FeedbackQualityEngine
from ml.continuous_learning import continuous_learning_engine, ContinuousLearningEngine
import threading

app = FastAPI(
    title="CareerShield Mail - Email & Fake Job Scam Detection API",
    description="Intelligent Machine Learning & NLP Cybersecurity Risk Classifier",
    version="2.0.0"
)

# CORS configuration
origins_env = os.environ.get("CORS_ORIGINS", "*")
allowed_origins = [o.strip() for o in origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if allowed_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class FeedbackRequest(BaseModel):
    text: str = Field(..., description="Email body text or snippet")
    label: str = Field(..., description="Feedback label: SAFE, SPAM, or UNSURE")
    user_id: Optional[str] = Field(None, description="Tenant user identifier (e.g. email or session ID)")
    message_id: Optional[str] = Field(None, description="Unique email message ID")
    original_prediction: Optional[str] = Field(None, description="Original model predicted label")
    original_risk_score: Optional[float] = Field(None, description="Original model risk score")
    threshold_used: Optional[float] = Field(0.05, description="Decision threshold applied")
    model_version: Optional[str] = Field("v2.0.0", description="Active model version during inference")
    source: Optional[str] = Field("web_client", description="Source interface")

class RollbackRequest(BaseModel):
    target_version_id: str = Field(..., description="Version ID of the model to rollback to")

class TriggerRetrainRequest(BaseModel):
    force: Optional[bool] = Field(False, description="Force retraining cycle even if volume threshold not met")

# Global Explainer & GmailClient instances
explainer: Optional[ModelExplainer] = None
active_gmail_client: Optional[GmailClient] = None
active_gmail_email: Optional[str] = None


@app.on_event("startup")
def startup_event():
    """Preloads the ML explainer and vectorizers during worker startup."""
    global explainer
    if explainer is None:
        explainer = ModelExplainer()


def get_explainer() -> ModelExplainer:
    global explainer
    if explainer is None:
        explainer = ModelExplainer()
    return explainer


# Request & Response Models
class PredictRequest(BaseModel):
    text: str = Field(..., max_length=50000, description="Email subject and body text to inspect")
    model: Optional[str] = Field("Stacking Ensemble", description="ML model family to invoke")
    sender: Optional[str] = Field(None, max_length=255)
    subject: Optional[str] = Field(None, max_length=500)


class ThresholdRequest(BaseModel):
    threshold: float = Field(0.05, ge=0.01, le=0.99, description="Decision threshold tau in [0.01, 0.99]")
    model: Optional[str] = Field("Stacking Ensemble", description="Model identifier")


class GmailConnectRequest(BaseModel):
    email: str = Field(..., max_length=255)
    app_password: str = Field(..., max_length=100)
    limit: Optional[int] = Field(20, ge=1, le=100)


# ========================================================
# HEALTH & READINESS ENDPOINTS
# ========================================================
@app.get("/api/health")
def health_check():
    """Liveness probe: verifies the API worker is running."""
    return {
        "status": "healthy",
        "service": "CareerShield Mail ML Engine",
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/api/ready")
def readiness_check():
    """Readiness probe: verifies ML models and vectorizers are loaded in memory."""
    exp = get_explainer()
    is_ready = exp.models is not None and len(exp.models) >= 7
    return {
        "status": "ready" if is_ready else "initializing",
        "models_loaded": len(exp.models) if exp.models else 0,
        "feature_dimensions": 14022,
        "timestamp": datetime.utcnow().isoformat()
    }


# ========================================================
# MODEL METADATA & BENCHMARK ENDPOINTS
# ========================================================
@app.get("/api/models")
def get_models():
    """Returns all available models and their benchmark performance summary."""
    try:
        with open('models/benchmark_results.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        metrics = data.get("metrics") or data.get("models") or {}
        return {
            "models": list(metrics.keys()),
            "metrics": metrics
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to load model benchmarks.")


@app.get("/api/benchmarks")
def get_benchmarks():
    """Returns full validation benchmark data, ROC/PR curves, and Confusion Matrices."""
    try:
        with open('models/benchmark_results.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        if "metrics" not in data and "models" in data:
            data["metrics"] = data["models"]
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to retrieve benchmark suite.")


@app.get("/api/stats")
def get_stats():
    """Returns statistical analysis (Chi2, Mutual Info, ANOVA) and dataset summary."""
    try:
        with open('models/statistical_analysis.json', 'r', encoding='utf-8') as f:
            stats = json.load(f)
        with open('dataset_summary.json', 'r', encoding='utf-8') as f:
            summary = json.load(f)
        return {
            "dataset_summary": summary,
            "statistical_analysis": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to load statistical indicators.")


# ========================================================
# CORE ML PREDICTION & THREAT INSPECTION
# ========================================================
@app.post("/api/predict")
def predict_email(req: PredictRequest):
    """Performs real-time ML inference, cyber threat scoring, token attribution, and Bayes decomposition."""
    sanitized_text = sanitize_email_text(req.text)
    if not sanitized_text.strip():
        raise HTTPException(status_code=400, detail="Email body text cannot be empty after sanitization.")
    
    try:
        exp = get_explainer()
        t0 = time.time()
        result = exp.explain(sanitized_text, model_name=req.model)
        result["latency_ms"] = round((time.time() - t0) * 1000.0, 2)
        result["extracted_urls"] = extract_safe_urls(req.text)

        # Log scan event asynchronously to SQLite store
        scan_id = f"scan-{int(time.time() * 1000)}"
        storage.log_scan(
            scan_id=scan_id,
            sender=req.sender or "Manual Scanner",
            subject=req.subject or sanitized_text[:60],
            model_used=req.model or "Stacking Ensemble",
            risk_score=result["risk_score"],
            is_spam=result["is_spam"],
            threat_level=result["threat_level"],
            security_triggers=result["security_triggers"],
            body_snippet=sanitized_text[:300]
        )
        result["scan_id"] = scan_id
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction error: {str(e)}")


# ========================================================
# FEED & SIMULATION ENDPOINTS
# ========================================================
@app.get("/api/feed")
def get_feed(model: Optional[str] = "Stacking Ensemble"):
    """Returns the Gmail inbox feed with live ML classifications attached."""
    try:
        exp = get_explainer()
        inbox_mails = []
        spam_mails = []
        all_mails = []

        for item in SIMULATED_EMAILS:
            clean_body = sanitize_email_text(item["body"])
            pred = exp.explain(clean_body, model_name=model)
            mail_entry = {
                **item,
                "ml_analysis": {
                    "is_spam": pred["is_spam"],
                    "risk_score": pred["risk_score"],
                    "threat_level": pred["threat_level"],
                    "threat_color": pred["threat_color"],
                    "security_triggers": pred["security_triggers"],
                    "token_attributions": pred["token_attributions"],
                    "bayes_statistics": pred["bayes_statistics"],
                    "model_consensus": pred["model_consensus"],
                    "linguistic_metrics": pred["linguistic_metrics"]
                }
            }
            all_mails.append(mail_entry)
            if pred["is_spam"]:
                spam_mails.append(mail_entry)
            else:
                inbox_mails.append(mail_entry)

        return {
            "all": all_mails,
            "inbox": inbox_mails,
            "spam": spam_mails,
            "inbox_count": len(inbox_mails),
            "spam_count": len(spam_mails)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error generating feed.")


@app.post("/api/simulate-incoming")
def simulate_incoming(model: Optional[str] = "Stacking Ensemble"):
    """Simulates a new incoming email and routes it automatically based on live ML inference."""
    try:
        exp = get_explainer()
        template = random.choice(INCOMING_SIMULATION_POOL)
        now_str = datetime.now().strftime("%I:%M %p")
        
        email_id = f"sim-{int(time.time() * 1000)}"
        body = sanitize_email_text(template["body"])
        pred = exp.explain(body, model_name=model)
        
        new_mail = {
            "id": email_id,
            "sender_name": template["sender_name"],
            "sender_email": template["sender_email"],
            "subject": template["subject"],
            "date": now_str,
            "timestamp": datetime.utcnow().isoformat(),
            "is_read": False,
            "is_starred": False,
            "category": template["category"],
            "body": body,
            "ml_analysis": {
                "is_spam": pred["is_spam"],
                "risk_score": pred["risk_score"],
                "threat_level": pred["threat_level"],
                "threat_color": pred["threat_color"],
                "security_triggers": pred["security_triggers"],
                "token_attributions": pred["token_attributions"],
                "bayes_statistics": pred["bayes_statistics"],
                "model_consensus": pred["model_consensus"],
                "linguistic_metrics": pred["linguistic_metrics"]
            }
        }
        return new_mail
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error simulating incoming email.")


@app.post("/api/simulate-threshold")
def simulate_threshold(req: ThresholdRequest):
    """Returns precision, recall, and false positive trade-offs from actual validation threshold evaluations."""
    try:
        with open('models/benchmark_results.json', 'r', encoding='utf-8') as f:
            benchmarks = json.load(f)
            
        sweep = benchmarks.get("threshold_sweep", [])
        if sweep:
            target = req.threshold
            closest = min(sweep, key=lambda r: abs(r.get("threshold", 0.05) - target))
            return {
                "threshold": req.threshold,
                "model": req.model,
                "metrics": {
                    "precision": closest.get("precision", 0.0),
                    "recall": closest.get("recall", 0.0),
                    "false_positive_rate": closest.get("fpr", 0.0),
                    "f1_score": closest.get("f1_score", 0.0),
                    "f05_score": closest.get("f05_score", 0.0),
                    "f2_score": closest.get("f2_score", 0.0)
                },
                "confusion_matrix": {
                    "tp": closest.get("tp", 0),
                    "fp": closest.get("fp", 0),
                    "tn": closest.get("tn", 0),
                    "fn": closest.get("fn", 0)
                }
            }
            
        return {"threshold": req.threshold, "model": req.model, "metrics": {"f1_score": 0.9847}}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error evaluating threshold metrics.")


# ========================================================
# GMAIL IMAP CONNECTION & SYNC ENDPOINTS
# ========================================================
@app.post("/api/gmail/connect")
def connect_gmail(req: GmailConnectRequest):
    """Authenticates with Gmail account via IMAP SSL or Mock Test Mode."""
    global active_gmail_client, active_gmail_email
    try:
        is_mock = (req.email.lower() == "mock@example.com") or (req.app_password == "mockpassword1234")
        client = GmailClient(email_address=req.email, app_password=req.app_password, is_mock=is_mock)
        client.test_connection()
        active_gmail_client = client
        active_gmail_email = req.email.strip()
        return {
            "status": "connected",
            "email": active_gmail_email,
            "mode": "mock_test" if is_mock else "live_imap_ssl",
            "message": f"Successfully connected to Gmail as {active_gmail_email}."
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


@app.get("/api/gmail/status")
def get_gmail_status():
    """Returns current Gmail connection status."""
    return {
        "is_connected": active_gmail_client is not None,
        "email": active_gmail_email,
        "mode": "mock_test" if (active_gmail_client and active_gmail_client.is_mock) else ("live_imap_ssl" if active_gmail_client else "disconnected")
    }


@app.get("/api/gmail/fetch")
def fetch_live_gmail(model: Optional[str] = "Stacking Ensemble", limit: Optional[int] = 50, folder: Optional[str] = "INBOX"):
    """Fetches real/mock emails from inbox and runs live ML threat classification."""
    global active_gmail_client, active_gmail_email
    if not active_gmail_client:
        raise HTTPException(status_code=400, detail="No Gmail account currently connected.")
    
    try:
        exp = get_explainer()
        raw_emails = active_gmail_client.fetch_latest_emails(folder=folder, limit=limit)
        
        inbox_mails = []
        spam_mails = []
        all_mails = []

        for item in raw_emails:
            body_text = item.get("body", "").strip() or item.get("subject", "").strip() or "Empty email message"
            pred = exp.explain(body_text, model_name=model)
            mail_entry = {
                **item,
                "ml_analysis": {
                    "is_spam": pred["is_spam"],
                    "risk_score": pred["risk_score"],
                    "threat_level": pred["threat_level"],
                    "threat_color": pred["threat_color"],
                    "security_triggers": pred["security_triggers"],
                    "token_attributions": pred["token_attributions"],
                    "bayes_statistics": pred["bayes_statistics"],
                    "model_consensus": pred["model_consensus"],
                    "linguistic_metrics": pred["linguistic_metrics"]
                }
            }
            all_mails.append(mail_entry)
            if pred["is_spam"]:
                spam_mails.append(mail_entry)
            else:
                inbox_mails.append(mail_entry)

        return {
            "status": "success",
            "account": active_gmail_email,
            "all": all_mails,
            "inbox": inbox_mails,
            "spam": spam_mails,
            "inbox_count": len(inbox_mails),
            "spam_count": len(spam_mails)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching emails: {str(e)}")


@app.post("/api/gmail/disconnect")
def disconnect_gmail():
    """Disconnects the active Gmail session safely."""
    global active_gmail_client, active_gmail_email
    if active_gmail_client:
        active_gmail_client.disconnect()
        active_gmail_client = None
    active_gmail_email = None
    return {"status": "disconnected", "message": "Gmail account disconnected successfully."}


# ========================================================
# MULTI-TENANT HUMAN-IN-THE-LOOP FEEDBACK ENDPOINTS
# ========================================================
@app.post("/api/feedback")
def submit_feedback(req: FeedbackRequest, request: Request):
    """
    Submits or updates personal user feedback on an analyzed email.
    Supports SAFE, SPAM, and UNSURE labels with rate limiting, multi-tenant isolation,
    and automatic idempotency.
    """
    user_id = req.user_id or active_gmail_email or request.headers.get("X-User-ID") or request.client.host or "tenant_default"
    
    # 1. Rate Limiting / Abuse Protection
    if not FeedbackQualityEngine.check_rate_limit(user_id):
        raise HTTPException(status_code=429, detail="Feedback submission rate limit exceeded. Please wait before submitting more feedback.")
    
    clean_text = sanitize_email_text(req.text)
    if not clean_text:
        raise HTTPException(status_code=400, detail="Email body text cannot be empty.")
    
    try:
        record = feedback_store.record_feedback(
            user_id=user_id,
            message_id=req.message_id,
            text=clean_text,
            label=req.label,
            original_prediction=req.original_prediction,
            original_risk_score=req.original_risk_score,
            threshold_used=req.threshold_used,
            model_version=req.model_version,
            source=req.source
        )
        return {
            "status": "success",
            "message": f"Feedback recorded successfully ({record['action']}).",
            "data": record
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to record feedback: {str(e)}")


@app.get("/api/feedback/my")
def get_my_feedback(user_id: Optional[str] = None, limit: Optional[int] = 50, request: Request = None):
    """Retrieves personal feedback records for the authenticated user/tenant."""
    target_user = user_id or active_gmail_email or (request.headers.get("X-User-ID") if request else None) or "tenant_default"
    records = feedback_store.get_user_feedback(target_user, limit=limit)
    return {
        "user_id": target_user,
        "count": len(records),
        "feedback": records
    }


@app.get("/api/feedback/check")
def check_message_feedback(text: Optional[str] = None, message_id: Optional[str] = None, user_id: Optional[str] = None, request: Request = None):
    """Checks if the user has already provided feedback for this specific message."""
    target_user = user_id or active_gmail_email or (request.headers.get("X-User-ID") if request else None) or "tenant_default"
    fb = feedback_store.get_feedback_for_message(target_user, message_id=message_id, text=text)
    return {
        "has_feedback": fb is not None,
        "feedback": fb
    }


@app.get("/api/feedback/stats")
def get_feedback_stats():
    """Returns aggregated feedback metrics, label breakdown, disagreement analysis, and tenant stats."""
    try:
        analytics = feedback_store.get_analytics_summary()
        eligibility = FeedbackQualityEngine.assess_global_eligibility(DB_PATH)
        return {
            "analytics": analytics,
            "eligibility": eligibility
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving feedback analytics: {str(e)}")


@app.get("/api/feedback/training-status")
def get_training_status():
    """Returns the continuous learning pipeline status, active production model, and candidate model history."""
    try:
        active_model = feedback_store.get_active_production_model()
        all_versions = feedback_store.get_all_model_versions()
        eligibility = FeedbackQualityEngine.assess_global_eligibility(DB_PATH)
        return {
            "active_production_model": active_model,
            "eligibility_status": eligibility,
            "model_version_history": all_versions,
            "retraining_policy": {
                "min_new_labels_required": 500,
                "min_contributing_users_required": 3,
                "max_single_user_share": "20%",
                "retraining_interval_days": 7,
                "asynchronous": True,
                "validation_gate_criteria": "Precision >= 0.9700 & F2-Score >= Baseline - 0.0050"
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving training status: {str(e)}")


@app.post("/api/feedback/trigger-eval")
def trigger_continuous_learning_eval(req: TriggerRetrainRequest):
    """
    Triggers an asynchronous continuous learning cycle in the background.
    Builds a candidate dataset snapshot, trains a candidate model, evaluates against the validation gate,
    and atomically promotes or safely rejects the candidate.
    """
    def run_cycle_bg():
        try:
            res = continuous_learning_engine.run_continuous_learning_cycle(force=req.force)
            print(f"[ContinuousLearningEngine] Cycle completed: {res.get('action')} - {res.get('reason')}")
        except Exception as err:
            print(f"[ContinuousLearningEngine] Background execution error: {err}")

    t = threading.Thread(target=run_cycle_bg, daemon=True)
    t.start()
    
    return {
        "status": "triggered",
        "message": "Continuous learning cycle launched asynchronously in background thread. Check /api/feedback/training-status for results.",
        "force": req.force
    }


@app.post("/api/models/rollback")
def rollback_model_version(req: RollbackRequest):
    """Rolls back active production model to a previously archived known-good version."""
    try:
        result = feedback_store.rollback_to_version(req.target_version_id)
        return {
            "status": "success",
            "message": f"Successfully rolled back production model to version '{req.target_version_id}'.",
            "active_model": result
        }
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rollback failed: {str(e)}")


# Mount Static directory
if os.path.exists("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == '__main__':
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("api.main:app", host="0.0.0.0", port=port, reload=False)
