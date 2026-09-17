import os
import json
import sqlite3
import hashlib
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

DB_PATH = os.environ.get("CAREERSHIELD_DB_PATH", os.environ.get("CYBERSHIELD_DB_PATH", "data/careershield_store.db" if os.path.exists("data/careershield_store.db") else ("data/cybershield_store.db" if os.path.exists("data/cybershield_store.db") else "data/careershield_store.db")))


def compute_message_hash(text: str) -> str:
    """Computes a canonical SHA-256 hash of normalized text for deduplication and conflict tracking."""
    normalized = " ".join((text or "").lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def init_feedback_schema(db_path: str = DB_PATH):
    """Initializes SQLite schema for multi-tenant feedback records and versioned model registry."""
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        # 1. Feedback Records Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feedback_records (
                feedback_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                message_id TEXT NOT NULL,
                message_hash TEXT NOT NULL,
                text_snippet TEXT,
                label TEXT NOT NULL CHECK(label IN ('SAFE', 'SPAM', 'UNSURE')),
                original_prediction TEXT,
                original_risk_score REAL,
                threshold_used REAL,
                model_version TEXT,
                source TEXT DEFAULT 'direct_scan',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                is_eligible INTEGER DEFAULT 0,
                review_status TEXT DEFAULT 'pending' CHECK(review_status IN ('pending', 'accepted', 'rejected')),
                conflict_status TEXT DEFAULT 'none' CHECK(conflict_status IN ('none', 'user_updated', 'cross_user_conflict')),
                dataset_version TEXT,
                UNIQUE(user_id, message_hash)
            )
        ''')
        
        # Indexes for fast lookup and multi-tenant isolation
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_fb_user ON feedback_records(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_fb_hash ON feedback_records(message_hash)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_fb_eligible ON feedback_records(is_eligible, label)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_fb_created ON feedback_records(created_at)')

        # 2. Model Versions Registry Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS model_versions (
                version_id TEXT PRIMARY KEY,
                model_name TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('production', 'candidate', 'rejected', 'archived')),
                dataset_version TEXT NOT NULL,
                metrics_json TEXT NOT NULL,
                validation_f1 REAL NOT NULL,
                validation_f2 REAL NOT NULL,
                validation_precision REAL NOT NULL,
                validation_recall REAL NOT NULL,
                threshold REAL NOT NULL,
                created_at TEXT NOT NULL,
                promoted_at TEXT,
                rejection_reason TEXT,
                artifact_path TEXT
            )
        ''')
        
        # 3. Continuous Learning Run Logs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS continuous_learning_runs (
                run_id TEXT PRIMARY KEY,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status TEXT NOT NULL,
                total_feedback INTEGER DEFAULT 0,
                eligible_feedback INTEGER DEFAULT 0,
                contributing_users INTEGER DEFAULT 0,
                candidate_version TEXT,
                gate_result TEXT,
                details_json TEXT
            )
        ''')

        # Insert baseline production model if not already present
        cursor.execute("SELECT COUNT(*) FROM model_versions WHERE status = 'production'")
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO model_versions 
                (version_id, model_name, status, dataset_version, metrics_json, validation_f1, validation_f2, validation_precision, validation_recall, threshold, created_at, promoted_at, artifact_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                "v2.0.0-frozen",
                "Deep Neural Net (MLP)",
                "production",
                "master_v2.0",
                json.dumps({
                    "accuracy": 0.9854,
                    "precision": 0.9778,
                    "recall": 0.9917,
                    "f1_score": 0.9847,
                    "f2_score": 0.9889,
                    "roc_auc": 0.9986,
                    "brier_score": 0.0125
                }),
                0.9847,
                0.9889,
                0.9778,
                0.9917,
                0.050,
                datetime.utcnow().isoformat(),
                datetime.utcnow().isoformat(),
                "models/trained_models.joblib"
            ))

        conn.commit()


class FeedbackStore:
    """Manages multi-tenant feedback storage, idempotency, user isolation, and model registry."""
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        init_feedback_schema(self.db_path)

    def record_feedback(self, user_id: str, message_id: str, text: str, label: str,
                        original_prediction: Optional[str] = None,
                        original_risk_score: Optional[float] = None,
                        threshold_used: Optional[float] = 0.05,
                        model_version: Optional[str] = "v2.0.0",
                        source: Optional[str] = "direct_scan") -> Dict[str, Any]:
        """
        Idempotently inserts or updates a user's feedback.
        If the user changes their label (e.g. SPAM -> SAFE), the existing record is updated.
        """
        label = label.upper().strip()
        if label not in ("SAFE", "SPAM", "UNSURE"):
            raise ValueError(f"Invalid feedback label: '{label}'. Must be SAFE, SPAM, or UNSURE.")

        user_id = (user_id or "anonymous_tenant").strip().lower()
        message_id = (message_id or f"msg-{int(time.time()*1000)}").strip()
        msg_hash = compute_message_hash(text)
        now_iso = datetime.utcnow().isoformat()
        snippet = (text or "").strip()[:400]

        # UNSURE is never directly eligible for training
        # SAFE and SPAM are potentially eligible pending multi-user QC checks
        is_eligible = 1 if label in ("SAFE", "SPAM") else 0

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Check for existing feedback by this user on this message hash
            cursor.execute(
                "SELECT feedback_id, label, created_at FROM feedback_records WHERE user_id = ? AND message_hash = ?",
                (user_id, msg_hash)
            )
            existing = cursor.fetchone()

            if existing:
                feedback_id, old_label, created_at = existing
                conflict_status = "user_updated" if old_label != label else "none"
                cursor.execute('''
                    UPDATE feedback_records
                    SET label = ?, is_eligible = ?, updated_at = ?, conflict_status = ?,
                        original_prediction = COALESCE(?, original_prediction),
                        original_risk_score = COALESCE(?, original_risk_score),
                        threshold_used = COALESCE(?, threshold_used),
                        model_version = COALESCE(?, model_version),
                        text_snippet = ?
                    WHERE feedback_id = ?
                ''', (
                    label, is_eligible, now_iso, conflict_status,
                    original_prediction, original_risk_score, threshold_used, model_version, snippet,
                    feedback_id
                ))
                action = "updated"
            else:
                feedback_id = f"fb-{msg_hash[:12]}-{hashlib.md5(f'{user_id}-{time.time()}'.encode()).hexdigest()[:8]}"
                cursor.execute('''
                    INSERT INTO feedback_records
                    (feedback_id, user_id, message_id, message_hash, text_snippet, label,
                     original_prediction, original_risk_score, threshold_used, model_version,
                     source, created_at, updated_at, is_eligible, review_status, conflict_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', 'none')
                ''', (
                    feedback_id, user_id, message_id, msg_hash, snippet, label,
                    original_prediction, original_risk_score, threshold_used, model_version,
                    source, now_iso, now_iso, is_eligible
                ))
                action = "created"

            conn.commit()

        # Check for cross-user conflicts on this message hash asynchronously / inline
        self._check_cross_user_conflicts(msg_hash)

        return {
            "feedback_id": feedback_id,
            "user_id": user_id,
            "message_id": message_id,
            "message_hash": msg_hash,
            "label": label,
            "action": action,
            "is_eligible": bool(is_eligible),
            "updated_at": now_iso
        }

    def _check_cross_user_conflicts(self, message_hash: str):
        """Flags cross-user disagreement (e.g. User A says SPAM, User B says SAFE) and updates eligibility."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT DISTINCT label FROM feedback_records WHERE message_hash = ? AND label IN ('SAFE', 'SPAM')",
                (message_hash,)
            )
            labels = [r[0] for r in cursor.fetchall()]
            
            has_conflict = len(labels) > 1
            conflict_val = "cross_user_conflict" if has_conflict else "none"
            # If there is an unresolved cross-user conflict, mark is_eligible = 0
            eligible_val = 0 if has_conflict else 1

            cursor.execute('''
                UPDATE feedback_records
                SET conflict_status = ?, is_eligible = CASE WHEN label = 'UNSURE' THEN 0 ELSE ? END
                WHERE message_hash = ?
            ''', (conflict_val, eligible_val, message_hash))
            conn.commit()

    def get_user_feedback(self, user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieves personal feedback records for a specific user (strict tenant isolation)."""
        user_id = user_id.strip().lower()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT feedback_id, message_id, message_hash, text_snippet, label,
                       original_prediction, original_risk_score, threshold_used,
                       model_version, created_at, updated_at, is_eligible, conflict_status
                FROM feedback_records
                WHERE user_id = ?
                ORDER BY updated_at DESC LIMIT ?
            ''', (user_id, limit))
            return [dict(r) for r in cursor.fetchall()]

    def get_feedback_for_message(self, user_id: str, message_id: str = None, text: str = None) -> Optional[Dict[str, Any]]:
        """Finds if this user has already provided feedback for a specific email or text."""
        user_id = user_id.strip().lower()
        msg_hash = compute_message_hash(text) if text else None
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if msg_hash:
                cursor.execute(
                    "SELECT * FROM feedback_records WHERE user_id = ? AND message_hash = ?",
                    (user_id, msg_hash)
                )
            elif message_id:
                cursor.execute(
                    "SELECT * FROM feedback_records WHERE user_id = ? AND message_id = ?",
                    (user_id, message_id)
                )
            else:
                return None
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_analytics_summary(self) -> Dict[str, Any]:
        """Computes comprehensive feedback statistics and quality metrics across tenants."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Label counts
            cursor.execute("SELECT label, COUNT(*) FROM feedback_records GROUP BY label")
            counts = {k: 0 for k in ["SAFE", "SPAM", "UNSURE"]}
            for row in cursor.fetchall():
                counts[row[0]] = row[1]

            # Total and unique stats
            cursor.execute("SELECT COUNT(*), COUNT(DISTINCT user_id), COUNT(DISTINCT message_hash) FROM feedback_records")
            tot, tot_users, tot_msgs = cursor.fetchone()

            # Eligible for training
            cursor.execute("SELECT COUNT(*) FROM feedback_records WHERE is_eligible = 1")
            eligible_cnt = cursor.fetchone()[0]

            # Conflicting records
            cursor.execute("SELECT COUNT(*) FROM feedback_records WHERE conflict_status = 'cross_user_conflict'")
            conflict_cnt = cursor.fetchone()[0]

            # Model vs User disagreement analysis
            cursor.execute('''
                SELECT 
                    SUM(CASE WHEN original_prediction = 'SPAM' AND label = 'SAFE' THEN 1 ELSE 0 END) as false_positive_reports,
                    SUM(CASE WHEN original_prediction = 'SAFE' AND label = 'SPAM' THEN 1 ELSE 0 END) as false_negative_reports,
                    SUM(CASE WHEN (original_prediction = 'SPAM' AND label = 'SPAM') OR (original_prediction = 'SAFE' AND label = 'SAFE') THEN 1 ELSE 0 END) as agreements
                FROM feedback_records
                WHERE label IN ('SAFE', 'SPAM') AND original_prediction IS NOT NULL
            ''')
            row = cursor.fetchone()
            disagreement = {
                "user_reported_false_positives": row[0] or 0,
                "user_reported_false_negatives": row[1] or 0,
                "user_agreements": row[2] or 0
            }

            # Top contributing users (anonymized/aggregated)
            cursor.execute('''
                SELECT user_id, COUNT(*) as cnt, SUM(is_eligible) as eligible_cnt
                FROM feedback_records
                GROUP BY user_id
                ORDER BY cnt DESC LIMIT 10
            ''')
            user_contributions = [
                {"user_id": r[0], "total_feedback": r[1], "eligible_feedback": r[2]}
                for r in cursor.fetchall()
            ]

            return {
                "total_feedback": tot,
                "unique_users": tot_users,
                "unique_messages": tot_msgs,
                "label_distribution": counts,
                "eligible_for_training": eligible_cnt,
                "conflicting_samples": conflict_cnt,
                "disagreement_analysis": disagreement,
                "top_contributing_users": user_contributions
            }

    def get_active_production_model(self) -> Dict[str, Any]:
        """Returns metadata for the currently active production model."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM model_versions WHERE status = 'production' ORDER BY rowid DESC LIMIT 1")
            row = cursor.fetchone()
            if not row:
                return {
                    "version_id": "v2.0.0-frozen",
                    "model_name": "Deep Neural Net (MLP)",
                    "status": "production",
                    "threshold": 0.05
                }
            res = dict(row)
            if res.get("metrics_json"):
                res["metrics"] = json.loads(res["metrics_json"])
            return res

    def get_all_model_versions(self) -> List[Dict[str, Any]]:
        """Returns full version history of all production, candidate, and archived models."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM model_versions ORDER BY created_at DESC")
            results = []
            for r in cursor.fetchall():
                item = dict(r)
                if item.get("metrics_json"):
                    item["metrics"] = json.loads(item["metrics_json"])
                results.append(item)
            return results

    def register_candidate_model(self, version_id: str, model_name: str, dataset_version: str,
                                 metrics: Dict[str, Any], threshold: float, artifact_path: str) -> None:
        """Registers a newly trained candidate model awaiting validation gate evaluation."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO model_versions
                (version_id, model_name, status, dataset_version, metrics_json,
                 validation_f1, validation_f2, validation_precision, validation_recall,
                 threshold, created_at, artifact_path)
                VALUES (?, ?, 'candidate', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                version_id,
                model_name,
                dataset_version,
                json.dumps(metrics),
                metrics.get("f1_score", 0.0),
                metrics.get("f2_score", 0.0),
                metrics.get("precision", 0.0),
                metrics.get("recall", 0.0),
                threshold,
                datetime.utcnow().isoformat(),
                artifact_path
            ))
            conn.commit()

    def promote_candidate_model(self, candidate_version_id: str) -> None:
        """Atomically promotes a candidate model to production and archives the prior production model."""
        now_iso = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Archive current production models
            cursor.execute("UPDATE model_versions SET status = 'archived' WHERE status = 'production'")
            # Promote candidate
            cursor.execute('''
                UPDATE model_versions
                SET status = 'production', promoted_at = ?
                WHERE version_id = ?
            ''', (now_iso, candidate_version_id))
            conn.commit()

    def reject_candidate_model(self, candidate_version_id: str, reason: str) -> None:
        """Marks a candidate model as rejected with the recorded reason."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE model_versions
                SET status = 'rejected', rejection_reason = ?
                WHERE version_id = ?
            ''', (reason, candidate_version_id))
            conn.commit()

    def rollback_to_version(self, target_version_id: str) -> Dict[str, Any]:
        """Rolls back active production model to a previously archived known-good version."""
        now_iso = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM model_versions WHERE version_id = ?", (target_version_id,))
            target = cursor.fetchone()
            if not target:
                raise ValueError(f"Target model version '{target_version_id}' not found in registry.")

            # Archive current production models
            cursor.execute("UPDATE model_versions SET status = 'archived' WHERE status = 'production'")
            # Set target to production
            cursor.execute('''
                UPDATE model_versions
                SET status = 'production', promoted_at = ?
                WHERE version_id = ?
            ''', (now_iso, target_version_id))
            conn.commit()
            
            res = dict(target)
            res["status"] = "production"
            res["promoted_at"] = now_iso
            return res


feedback_store = FeedbackStore()
