import os
import sys
import shutil
import json
import joblib
import time
import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, fbeta_score,
    roc_auc_score, average_precision_score, brier_score_loss, confusion_matrix
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml.features import build_feature_pipeline
from ml.preprocess import clean_text_for_nlp

def execute_phase0_and_phase1():
    print("=" * 80)
    print("CAREERSHIELD ML: EXECUTING PHASE 0 (INTEGRITY) & PHASE 1 (BASELINE EXPERIMENT)")
    print("=" * 80)
    
    os.makedirs("reports", exist_ok=True)
    os.makedirs("models", exist_ok=True)
    
    if os.path.exists("models/benchmark_results.json"):
        shutil.copy("models/benchmark_results.json", "models/baseline_benchmark_results.json")
        print("  [Phase 0] Preserved baseline benchmark copy to models/baseline_benchmark_results.json")
        
    train_df = pd.read_parquet("splits/train.parquet")
    val_df = pd.read_parquet("splits/validation.parquet")
    test_df = pd.read_parquet("splits/test.parquet")
    unlabeled_df = pd.read_parquet("splits/unlabelled_holdout.parquet") if os.path.exists("splits/unlabelled_holdout.parquet") else None
    
    print(f"  [Phase 0] Verified Partitions: Train={len(train_df):,}, Val={len(val_df):,}, Test={len(test_df):,}, Holdout={len(unlabeled_df):,}")
    
    word_vec = joblib.load("models/word_vectorizer.joblib")
    char_vec = joblib.load("models/char_vectorizer.joblib")
    sec_extractor = joblib.load("models/security_extractor.joblib")
    
    n_word = len(word_vec.get_feature_names_out())
    n_char = len(char_vec.get_feature_names_out())
    n_sec = len(sec_extractor.feature_names_) if hasattr(sec_extractor, "feature_names_") else 22
    total_dim = n_word + n_char + n_sec
    print(f"  [Phase 0] Feature Pipeline: Word={n_word:,} + Char={n_char:,} + Sec={n_sec} = {total_dim:,} features")
    
    t0_t = time.time()
    print("  [Phase 1] Transforming validation & test datasets...")
    cleaned_val = [clean_text_for_nlp(t) for t in val_df["text"].tolist()]
    X_val_w = word_vec.transform(cleaned_val)
    X_val_c = char_vec.transform(cleaned_val)
    X_val_s = sec_extractor.transform(val_df["text"].tolist())
    X_val = sparse.hstack([X_val_w, X_val_c, X_val_s]).tocsr()
    y_val = val_df["label"].astype(int).values
    
    cleaned_test = [clean_text_for_nlp(t) for t in test_df["text"].tolist()]
    X_test_w = word_vec.transform(cleaned_test)
    X_test_c = char_vec.transform(cleaned_test)
    X_test_s = sec_extractor.transform(test_df["text"].tolist())
    X_test = sparse.hstack([X_test_w, X_test_c, X_test_s]).tocsr()
    y_test = test_df["label"].astype(int).values
    print(f"  [Phase 1] Feature transformation complete in {time.time() - t0_t:.2f}s")
    
    trained_models = joblib.load("models/trained_models.joblib")
    
    baseline_eval = {
        "dataset_metadata": {
            "train_samples": len(train_df),
            "val_samples": len(val_df),
            "test_samples": len(test_df),
            "total_labeled": len(train_df) + len(val_df) + len(test_df),
            "unlabeled_holdout": len(unlabeled_df) if unlabeled_df is not None else 0,
            "feature_dimension": total_dim,
            "threat_ratio_train": round(float(np.mean(train_df["label"].astype(int).values)), 4),
            "threat_ratio_val": round(float(np.mean(y_val)), 4),
            "threat_ratio_test": round(float(np.mean(y_test)), 4)
        },
        "validation_metrics": {},
        "test_metrics": {}
    }
    
    print("\n--- PHASE 1: OFFICIAL BASELINE EVALUATION ---")
    print(f"{'Model Name':<26} | {'Val F1':<8} | {'Val F2':<8} | {'Val AUC':<8} | {'Test F1':<8} | {'Test F2':<8} | {'Test AUC':<8} | {'Lat(ms)':<7}")
    print("-" * 105)
    
    for name, model in trained_models.items():
        t0_v = time.time()
        if hasattr(model, "predict_proba"):
            val_probs = model.predict_proba(X_val)[:, 1]
        elif hasattr(model, "decision_function"):
            df_s = model.decision_function(X_val)
            val_probs = (df_s - df_s.min()) / (df_s.max() - df_s.min() + 1e-8)
        else:
            val_probs = model.predict(X_val).astype(float)
        val_lat = (time.time() - t0_v) / len(y_val) * 1000.0
        val_preds = (val_probs >= 0.50).astype(int)
        
        cm_v = confusion_matrix(y_val, val_preds)
        tn_v, fp_v, fn_v, tp_v = int(cm_v[0,0]), int(cm_v[0,1]), int(cm_v[1,0]), int(cm_v[1,1])
        
        val_metrics = {
            "accuracy": round(float(accuracy_score(y_val, val_preds)), 4),
            "precision": round(float(precision_score(y_val, val_preds, zero_division=0)), 4),
            "recall": round(float(recall_score(y_val, val_preds, zero_division=0)), 4),
            "f1_score": round(float(f1_score(y_val, val_preds, zero_division=0)), 4),
            "f2_score": round(float(fbeta_score(y_val, val_preds, beta=2, zero_division=0)), 4),
            "roc_auc": round(float(roc_auc_score(y_val, val_probs)), 4),
            "pr_auc": round(float(average_precision_score(y_val, val_probs)), 4),
            "brier_score": round(float(brier_score_loss(y_val, val_probs)), 4),
            "latency_ms_per_sample": round(float(val_lat), 4),
            "tp": tp_v, "fp": fp_v, "tn": tn_v, "fn": fn_v
        }
        baseline_eval["validation_metrics"][name] = val_metrics
        
        t0_t = time.time()
        if hasattr(model, "predict_proba"):
            test_probs = model.predict_proba(X_test)[:, 1]
        elif hasattr(model, "decision_function"):
            df_st = model.decision_function(X_test)
            test_probs = (df_st - df_st.min()) / (df_st.max() - df_st.min() + 1e-8)
        else:
            test_probs = model.predict(X_test).astype(float)
        test_lat = (time.time() - t0_t) / len(y_test) * 1000.0
        test_preds = (test_probs >= 0.50).astype(int)
        
        cm_t = confusion_matrix(y_test, test_preds)
        tn_t, fp_t, fn_t, tp_t = int(cm_t[0,0]), int(cm_t[0,1]), int(cm_t[1,0]), int(cm_t[1,1])
        
        test_metrics = {
            "accuracy": round(float(accuracy_score(y_test, test_preds)), 4),
            "precision": round(float(precision_score(y_test, test_preds, zero_division=0)), 4),
            "recall": round(float(recall_score(y_test, test_preds, zero_division=0)), 4),
            "f1_score": round(float(f1_score(y_test, test_preds, zero_division=0)), 4),
            "f2_score": round(float(fbeta_score(y_test, test_preds, beta=2, zero_division=0)), 4),
            "roc_auc": round(float(roc_auc_score(y_test, test_probs)), 4),
            "pr_auc": round(float(average_precision_score(y_test, test_probs)), 4),
            "brier_score": round(float(brier_score_loss(y_test, test_probs)), 4),
            "latency_ms_per_sample": round(float(test_lat), 4),
            "tp": tp_t, "fp": fp_t, "tn": tn_t, "fn": fn_t
        }
        baseline_eval["test_metrics"][name] = test_metrics
        
        print(f"{name:<26} | {val_metrics['f1_score']:<8.4f} | {val_metrics['f2_score']:<8.4f} | {val_metrics['roc_auc']:<8.4f} | {test_metrics['f1_score']:<8.4f} | {test_metrics['f2_score']:<8.4f} | {test_metrics['roc_auc']:<8.4f} | {test_lat:<7.4f}")

    with open("reports/phase1_baseline_experiment.json", "w", encoding="utf-8") as f:
        json.dump(baseline_eval, f, indent=2)
    print("\n[SUCCESS] Phase 0 & Phase 1 Complete. Saved baseline results to reports/phase1_baseline_experiment.json")
    return baseline_eval

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    execute_phase0_and_phase1()
