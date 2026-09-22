import os
import sys
import json
import time
import shutil
import hashlib
import sqlite3
import joblib
import numpy as np
import pandas as pd
from scipy import sparse
from datetime import datetime
from typing import Dict, Any, Tuple, Optional, List

from sklearn.neural_network import MLPClassifier
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, fbeta_score,
    roc_auc_score, average_precision_score, brier_score_loss, confusion_matrix
)

from ml.features import build_feature_pipeline
from ml.preprocess import clean_text_for_nlp
from ml.feedback_store import feedback_store, DB_PATH
from ml.feedback_quality import FeedbackQualityEngine

CANDIDATE_DATASETS_DIR = "data/candidate_datasets"
CANDIDATE_MODELS_DIR = "models/candidates"
os.makedirs(CANDIDATE_DATASETS_DIR, exist_ok=True)
os.makedirs(CANDIDATE_MODELS_DIR, exist_ok=True)


class ContinuousLearningEngine:
    """Manages immutable candidate dataset snapshotting, candidate model training, validation gates, and promotion/rollback."""

    @staticmethod
    def create_candidate_dataset_snapshot(curated_feedback_samples: List[Dict[str, Any]]) -> Tuple[str, str, int]:
        """
        Creates a new immutable candidate dataset parquet snapshot by combining
        the frozen base train split with verified, capped multi-user feedback samples.
        Original splits/train.parquet is NEVER destructively altered.
        """
        base_train_df = pd.read_parquet("splits/train.parquet")
        
        timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        dataset_version = f"dataset_v2.1_{timestamp_str}"
        snapshot_filename = f"candidate_{dataset_version}.parquet"
        snapshot_path = os.path.join(CANDIDATE_DATASETS_DIR, snapshot_filename)

        if curated_feedback_samples:
            fb_df = pd.DataFrame([{
                "text": s["text"] if s.get("text") else "Sample text placeholder",
                "label": int(s["label"])
            } for s in curated_feedback_samples])
            
            candidate_df = pd.concat([base_train_df, fb_df], ignore_index=True)
        else:
            candidate_df = base_train_df.copy()

        candidate_df.to_parquet(snapshot_path, index=False)

        if curated_feedback_samples:
            fb_ids = [s["feedback_id"] for s in curated_feedback_samples if "feedback_id" in s]
            if fb_ids:
                with sqlite3.connect(DB_PATH) as conn:
                    cursor = conn.cursor()
                    placeholders = ",".join("?" for _ in fb_ids)
                    cursor.execute(f'''
                        UPDATE feedback_records
                        SET dataset_version = ?
                        WHERE feedback_id IN ({placeholders})
                    ''', [dataset_version] + fb_ids)
                    conn.commit()

        return dataset_version, snapshot_path, len(candidate_df)

    @classmethod
    def train_candidate_model(cls, candidate_dataset_path: str, dataset_version: str) -> Tuple[str, Dict[str, Any], str]:
        """
        Trains a candidate Deep Neural Net (MLP) on the candidate dataset using the
        exact 14,022-dimensional NLP & cybersecurity feature extraction pipeline.
        """
        version_id = f"v2.1.0-cand-{int(time.time())}"
        
        train_df = pd.read_parquet(candidate_dataset_path)
        val_df = pd.read_parquet("splits/validation.parquet")

        X_train_raw = train_df["text"].tolist()
        y_train = train_df["label"].astype(int).values

        X_val_raw = val_df["text"].tolist()
        y_val = val_df["label"].astype(int).values

        word_vec, char_vec, sec_extractor = build_feature_pipeline()

        cleaned_train = [clean_text_for_nlp(t) for t in X_train_raw]
        cleaned_val = [clean_text_for_nlp(t) for t in X_val_raw]

        X_word_train = word_vec.fit_transform(cleaned_train)
        X_word_val = word_vec.transform(cleaned_val)

        X_char_train = char_vec.fit_transform(cleaned_train)
        X_char_val = char_vec.transform(cleaned_val)

        X_sec_train = sec_extractor.fit_transform(X_train_raw)
        X_sec_val = sec_extractor.transform(X_val_raw)

        X_train_combined = sparse.hstack([X_word_train, X_char_train, X_sec_train]).tocsr()
        X_val_combined = sparse.hstack([X_word_val, X_char_val, X_sec_val]).tocsr()

        clf = MLPClassifier(
            hidden_layer_sizes=(128, 64),
            activation='relu',
            solver='adam',
            alpha=0.001,
            learning_rate_init=0.001,
            max_iter=25,
            early_stopping=True,
            random_state=42
        )
        clf.fit(X_train_combined, y_train)

        val_probs = clf.predict_proba(X_val_combined)[:, 1]
        threshold = 0.050
        val_preds = (val_probs >= threshold).astype(int)

        metrics = {
            "accuracy": round(float(accuracy_score(y_val, val_preds)), 4),
            "precision": round(float(precision_score(y_val, val_preds, zero_division=0)), 4),
            "recall": round(float(recall_score(y_val, val_preds, zero_division=0)), 4),
            "f1_score": round(float(f1_score(y_val, val_preds, zero_division=0)), 4),
            "f2_score": round(float(fbeta_score(y_val, val_preds, beta=2, zero_division=0)), 4),
            "roc_auc": round(float(roc_auc_score(y_val, val_probs)), 4),
            "pr_auc": round(float(average_precision_score(y_val, val_probs)), 4),
            "brier_score": round(float(brier_score_loss(y_val, val_probs)), 4)
        }

        artifact_path = os.path.join(CANDIDATE_MODELS_DIR, f"{version_id}.joblib")
        bundle = {
            "version_id": version_id,
            "dataset_version": dataset_version,
            "model": clf,
            "word_vectorizer": word_vec,
            "char_vectorizer": char_vec,
            "security_extractor": sec_extractor,
            "threshold": threshold,
            "metrics": metrics,
            "trained_at": datetime.utcnow().isoformat()
        }
        joblib.dump(bundle, artifact_path, compress=3)

        feedback_store.register_candidate_model(
            version_id=version_id,
            model_name="Deep Neural Net (MLP)",
            dataset_version=dataset_version,
            metrics=metrics,
            threshold=threshold,
            artifact_path=artifact_path
        )

        return version_id, metrics, artifact_path

    @classmethod
    def evaluate_validation_gate(cls, candidate_metrics: Dict[str, Any],
                                 baseline_production_metrics: Optional[Dict[str, Any]] = None) -> Tuple[bool, List[str]]:
        """
        Applies rigorous validation gates before any candidate model can be promoted:
        1. Precision >= 0.9700 (Strict anti-false-alarm protection).
        2. F2-Score >= Baseline F2 - 0.0050 (Recall & threat detection retention).
        3. ROC-AUC >= 0.9950.
        4. Brier Calibration Score <= 0.0200.
        """
        gate_failures = []
        
        cand_prec = candidate_metrics.get("precision", 0.0)
        cand_f2 = candidate_metrics.get("f2_score", 0.0)
        cand_auc = candidate_metrics.get("roc_auc", 0.0)
        cand_brier = candidate_metrics.get("brier_score", 1.0)

        if cand_prec < 0.9700:
            gate_failures.append(f"Precision Gate Failed: {cand_prec:.4f} < 0.9700 target (Risk of excessive false positives)")

        base_f2 = (baseline_production_metrics or {}).get("f2_score", 0.9880)
        if cand_f2 < (base_f2 - 0.0050):
            gate_failures.append(f"F2-Score Regression Gate Failed: {cand_f2:.4f} < {base_f2 - 0.0050:.4f} baseline threshold")

        if cand_auc < 0.9950:
            gate_failures.append(f"ROC-AUC Gate Failed: {cand_auc:.4f} < 0.9950")

        if cand_brier > 0.0200:
            gate_failures.append(f"Calibration Brier Score Gate Failed: {cand_brier:.4f} > 0.0200")

        passed = len(gate_failures) == 0
        return passed, gate_failures

    @classmethod
    def run_continuous_learning_cycle(cls, force: bool = False, max_feedback_samples: int = 500) -> Dict[str, Any]:
        """
        Executes a complete continuous learning cycle:
        1. Multi-user eligibility & anti-poisoning check.
        2. Immutable candidate dataset snapshot generation.
        3. Asynchronous candidate model training.
        4. Validation gate evaluation.
        5. Atomic promotion or safe rejection.
        """
        run_id = f"cl-run-{int(time.time())}"
        started_at = datetime.utcnow().isoformat()
        
        eligibility = FeedbackQualityEngine.assess_global_eligibility(DB_PATH)
        if not eligibility["eligible_for_retraining"] and not force:
            return {
                "run_id": run_id,
                "status": "skipped",
                "reason": eligibility["reason"],
                "eligibility_details": eligibility
            }

        curated_samples = FeedbackQualityEngine.extract_capped_candidate_samples(DB_PATH, max_total_samples=max_feedback_samples)

        dataset_version, snapshot_path, total_rows = cls.create_candidate_dataset_snapshot(curated_samples)

        candidate_version_id, candidate_metrics, artifact_path = cls.train_candidate_model(snapshot_path, dataset_version)

        active_prod = feedback_store.get_active_production_model()
        baseline_metrics = active_prod.get("metrics", {})
        passed_gate, failure_reasons = cls.evaluate_validation_gate(candidate_metrics, baseline_metrics)

        if passed_gate:
            feedback_store.promote_candidate_model(candidate_version_id)
            action_result = "PROMOTED_TO_PRODUCTION"
            final_reason = "Candidate model passed all precision, recall, ROC-AUC, and calibration gates."
        else:
            feedback_store.reject_candidate_model(candidate_version_id, "; ".join(failure_reasons))
            action_result = "REJECTED"
            final_reason = "; ".join(failure_reasons)

        run_summary = {
            "run_id": run_id,
            "started_at": started_at,
            "finished_at": datetime.utcnow().isoformat(),
            "status": "completed",
            "candidate_version_id": candidate_version_id,
            "dataset_version": dataset_version,
            "curated_feedback_samples_used": len(curated_samples),
            "total_candidate_dataset_size": total_rows,
            "candidate_metrics": candidate_metrics,
            "validation_gate_passed": passed_gate,
            "gate_failures": failure_reasons,
            "action": action_result,
            "reason": final_reason,
            "active_production_version": candidate_version_id if passed_gate else active_prod.get("version_id")
        }

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO continuous_learning_runs
                (run_id, started_at, finished_at, status, total_feedback, eligible_feedback, contributing_users, candidate_version, gate_result, details_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                run_id, started_at, run_summary["finished_at"], "completed",
                eligibility["total_eligible_samples"], len(curated_samples),
                eligibility["contributing_users"], candidate_version_id,
                action_result, json.dumps(run_summary)
            ))
            conn.commit()

        return run_summary


continuous_learning_engine = ContinuousLearningEngine()
