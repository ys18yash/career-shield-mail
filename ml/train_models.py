import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import time
import json
import joblib
import numpy as np
import pandas as pd
from scipy import sparse

from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, fbeta_score,
    roc_auc_score, average_precision_score, brier_score_loss,
    roc_curve, precision_recall_curve, confusion_matrix
)
from sklearn.naive_bayes import MultinomialNB
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier, VotingClassifier
from sklearn.neural_network import MLPClassifier
from xgboost import XGBClassifier

from ml.features import build_feature_pipeline, compute_statistical_tests
from ml.preprocess import clean_text_for_nlp

# Seed for reproducibility
RANDOM_STATE = 42
np.random.seed(RANDOM_STATE)
os.makedirs("models", exist_ok=True)


def load_splits():
    """Loads the leak-free train, validation, and test splits."""
    train_df = pd.read_parquet("splits/train.parquet")
    val_df = pd.read_parquet("splits/validation.parquet")
    test_df = pd.read_parquet("splits/test.parquet")
    return train_df, val_df, test_df


def train_and_benchmark_all():
    print("=" * 70, flush=True)
    print(">> CAREERSHIELD ML: LARGE-SCALE MULTI-MODEL BENCHMARK & TRAINING", flush=True)
    print("=" * 70, flush=True)
    
    train_df, val_df, test_df = load_splits()
    
    X_train_raw = train_df["text"].tolist()
    y_train = train_df["label"].astype(int).values
    
    X_val_raw = val_df["text"].tolist()
    y_val = val_df["label"].astype(int).values
    
    X_test_raw = test_df["text"].tolist()
    y_test = test_df["label"].astype(int).values
    
    print(f"Train Partition : {len(X_train_raw):6,d} samples (Threat: {np.sum(y_train == 1):,}, Safe: {np.sum(y_train == 0):,})", flush=True)
    print(f"Val Partition   : {len(X_val_raw):6,d} samples (Threat: {np.sum(y_val == 1):,}, Safe: {np.sum(y_val == 0):,})", flush=True)
    print(f"Test Partition  : {len(X_test_raw):6,d} samples (Threat: {np.sum(y_test == 1):,}, Safe: {np.sum(y_test == 0):,})", flush=True)
    
    # 1. Statistical Hypothesis Tests on Training Set
    print("\n[1/5] Running Statistical Hypothesis Testing (Chi2, Mutual Information, ANOVA)...", flush=True)
    stats_data = compute_statistical_tests(X_train_raw[:15000], y_train[:15000], top_n=30)
    with open("models/statistical_analysis.json", "w", encoding="utf-8") as f:
        json.dump(stats_data, f, indent=2)
    print("  -> Saved statistical analysis to models/statistical_analysis.json", flush=True)
    
    # 2. Fit Feature Extraction Pipeline on Train Only
    print("\n[2/5] Fitting NLP Vectorizers & Security Features on Train (Leakage-Safe)...", flush=True)
    t_feat = time.time()
    word_vec, char_vec, sec_extractor = build_feature_pipeline()
    
    cleaned_train = [clean_text_for_nlp(t) for t in X_train_raw]
    cleaned_val = [clean_text_for_nlp(t) for t in X_val_raw]
    cleaned_test = [clean_text_for_nlp(t) for t in X_test_raw]
    
    print("  -> Fitting Word TF-IDF (10,000 features)...", flush=True)
    X_word_train = word_vec.fit_transform(cleaned_train)
    X_word_val = word_vec.transform(cleaned_val)
    X_word_test = word_vec.transform(cleaned_test)
    
    print("  -> Fitting Char TF-IDF (4,000 features)...", flush=True)
    X_char_train = char_vec.fit_transform(cleaned_train)
    X_char_val = char_vec.transform(cleaned_val)
    X_char_test = char_vec.transform(cleaned_test)
    
    print("  -> Extracting Dense Security Signals (22 features)...", flush=True)
    X_sec_train = sec_extractor.fit_transform(X_train_raw)
    X_sec_val = sec_extractor.transform(X_val_raw)
    X_sec_test = sec_extractor.transform(X_test_raw)
    
    X_train_combined = sparse.hstack([X_word_train, X_char_train, X_sec_train]).tocsr()
    X_val_combined = sparse.hstack([X_word_val, X_char_val, X_sec_val]).tocsr()
    X_test_combined = sparse.hstack([X_word_test, X_char_test, X_sec_test]).tocsr()
    
    print(f"  -> Combined Feature Matrix: {X_train_combined.shape[1]:,d} features", flush=True)
    print(f"     [Word: {X_word_train.shape[1]:,d} | Char: {X_char_train.shape[1]:,d} | Cyber: {X_sec_train.shape[1]:,d}]", flush=True)
    print(f"  -> Preprocessing completed in {time.time() - t_feat:.1f}s", flush=True)
    
    # 3. Model Suite Definition
    print("\n[3/5] Initializing & Training Multi-Model Suite...", flush=True)
    
    base_models = {
        "Naive Bayes": MultinomialNB(alpha=0.1),
        "Logistic Regression": LogisticRegression(C=2.0, max_iter=1000, class_weight='balanced', solver='lbfgs', random_state=RANDOM_STATE, n_jobs=-1),
        "Support Vector Machine": CalibratedClassifierCV(LinearSVC(C=1.0, dual=False, random_state=RANDOM_STATE), cv=3),
        "Random Forest": RandomForestClassifier(n_estimators=50, max_depth=25, random_state=RANDOM_STATE, n_jobs=-1),
        "Extra Trees Ensemble": ExtraTreesClassifier(n_estimators=50, max_depth=25, random_state=RANDOM_STATE, n_jobs=-1),
        "XGBoost": XGBClassifier(n_estimators=50, max_depth=5, max_bin=32, colsample_bytree=0.2, subsample=0.8, tree_method='approx', eval_metric='logloss', random_state=RANDOM_STATE, n_jobs=-1),
        "Deep Neural Net (MLP)": MLPClassifier(hidden_layer_sizes=(128, 64), activation='relu', solver='adam', alpha=0.0001, max_iter=30, early_stopping=True, validation_fraction=0.1, random_state=RANDOM_STATE)
    }
    
    ensemble_estimators = [
        ('nb', MultinomialNB(alpha=0.1)),
        ('lr', LogisticRegression(C=2.0, max_iter=1000, class_weight='balanced', random_state=RANDOM_STATE, n_jobs=-1)),
        ('svm', CalibratedClassifierCV(LinearSVC(C=1.0, dual=False, random_state=RANDOM_STATE), cv=3)),
        ('rf', RandomForestClassifier(n_estimators=30, max_depth=20, random_state=RANDOM_STATE, n_jobs=-1)),
        ('xgb', XGBClassifier(n_estimators=30, max_depth=4, max_bin=32, colsample_bytree=0.2, subsample=0.8, tree_method='approx', eval_metric='logloss', random_state=RANDOM_STATE, n_jobs=-1)),
    ]
    
    models = dict(base_models)
    models["Stacking Ensemble"] = VotingClassifier(
        estimators=ensemble_estimators,
        voting='soft',
        n_jobs=-1
    )
    
    # 4. Train Models & Evaluate on Validation Set
    val_benchmark_results = {}
    test_benchmark_results = {}
    roc_curves = {}
    pr_curves = {}
    val_confusion_matrices = {}
    test_confusion_matrices = {}
    trained_models = {}
    val_probabilities = {}
    test_probabilities = {}
    
    print("\n--- BENCHMARKING ON VALIDATION PARTITION ---", flush=True)
    print(f"{'Model':<25} | {'Fit(s)':<7} | {'Val Acc':<7} | {'Val Prec':<8} | {'Val Rec':<8} | {'Val F1':<7} | {'Val F2':<7} | {'ROC-AUC':<7} | {'PR-AUC':<7} | {'FP':<5} | {'FN':<5}")
    print("-" * 115)
    
    for name, model in models.items():
        t0_fit = time.time()
        model.fit(X_train_combined, y_train)
        fit_time = time.time() - t0_fit
        trained_models[name] = model
        
        # Validation Inference & Probabilities
        t0_pred = time.time()
        if hasattr(model, "predict_proba"):
            val_probs = model.predict_proba(X_val_combined)[:, 1]
        elif hasattr(model, "decision_function"):
            df_scores = model.decision_function(X_val_combined)
            val_probs = (df_scores - df_scores.min()) / (df_scores.max() - df_scores.min() + 1e-8)
        else:
            val_probs = model.predict(X_val_combined).astype(float)
        latency_ms = (time.time() - t0_pred) / len(y_val) * 1000.0
        val_probabilities[name] = val_probs
        
        val_preds = (val_probs >= 0.50).astype(int)
        
        acc = accuracy_score(y_val, val_preds)
        prec = precision_score(y_val, val_preds, zero_division=0)
        rec = recall_score(y_val, val_preds, zero_division=0)
        f1 = f1_score(y_val, val_preds, zero_division=0)
        f2 = fbeta_score(y_val, val_preds, beta=2, zero_division=0)
        auc = roc_auc_score(y_val, val_probs)
        prauc = average_precision_score(y_val, val_probs)
        brier = brier_score_loss(y_val, val_probs)
        cm = confusion_matrix(y_val, val_preds)
        
        tn, fp, fn, tp = int(cm[0, 0]), int(cm[0, 1]), int(cm[1, 0]), int(cm[1, 1])
        val_confusion_matrices[name] = {"tn": tn, "fp": fp, "fn": fn, "tp": tp}
        
        val_benchmark_results[name] = {
            "accuracy": round(float(acc), 4),
            "precision": round(float(prec), 4),
            "recall": round(float(rec), 4),
            "f1_score": round(float(f1), 4),
            "f2_score": round(float(f2), 4),
            "roc_auc": round(float(auc), 4),
            "pr_auc": round(float(prauc), 4),
            "brier_score": round(float(brier), 4),
            "latency_ms": round(float(latency_ms), 3),
            "fit_time_sec": round(float(fit_time), 2),
            "fp": fp,
            "fn": fn,
            "tp": tp,
            "tn": tn
        }
        
        # Curves for visualization
        fpr, tpr, _ = roc_curve(y_val, val_probs)
        precision_pts, recall_pts, _ = precision_recall_curve(y_val, val_probs)
        step_roc = max(1, len(fpr) // 50)
        roc_curves[name] = {
            "fpr": [round(float(v), 4) for v in fpr[::step_roc]],
            "tpr": [round(float(v), 4) for v in tpr[::step_roc]]
        }
        step_pr = max(1, len(recall_pts) // 50)
        pr_curves[name] = {
            "recall": [round(float(v), 4) for v in recall_pts[::step_pr]],
            "precision": [round(float(v), 4) for v in precision_pts[::step_pr]]
        }
        
        print(f"{name:<25} | {fit_time:7.1f} | {acc:7.4f} | {prec:8.4f} | {rec:8.4f} | {f1:7.4f} | {f2:7.4f} | {auc:7.4f} | {prauc:7.4f} | {fp:5d} | {fn:5d}")

    # 5. Validation-Only Decision Threshold Optimization
    print("\n[4/5] Running Decision Threshold Optimization on VALIDATION Data...", flush=True)
    sorted_models = sorted(val_benchmark_results.items(), key=lambda x: (x[1]['f2_score'], x[1]['f1_score'], x[1]['pr_auc']), reverse=True)
    best_candidate_name = sorted_models[0][0]
    print(f"  -> Top Validation Candidate Model: {best_candidate_name} (Val F2: {val_benchmark_results[best_candidate_name]['f2_score']:.4f}, Val F1: {val_benchmark_results[best_candidate_name]['f1_score']:.4f})")
    
    candidate_val_probs = val_probabilities[best_candidate_name]
    threshold_grid = np.linspace(0.05, 0.95, 46)
    threshold_records = []
    
    best_tau = 0.50
    best_tau_f2 = 0.0
    
    for tau in threshold_grid:
        tau_preds = (candidate_val_probs >= tau).astype(int)
        p = precision_score(y_val, tau_preds, zero_division=0)
        r = recall_score(y_val, tau_preds, zero_division=0)
        f_1 = f1_score(y_val, tau_preds, zero_division=0)
        f_2 = fbeta_score(y_val, tau_preds, beta=2, zero_division=0)
        f_05 = fbeta_score(y_val, tau_preds, beta=0.5, zero_division=0)
        cm_tau = confusion_matrix(y_val, tau_preds)
        tn_t, fp_t, fn_t, tp_t = int(cm_tau[0, 0]), int(cm_tau[0, 1]), int(cm_tau[1, 0]), int(cm_tau[1, 1])
        fpr_t = fp_t / max(fp_t + tn_t, 1)
        
        record = {
            "threshold": round(float(tau), 3),
            "precision": round(float(p), 4),
            "recall": round(float(r), 4),
            "f1_score": round(float(f_1), 4),
            "f2_score": round(float(f_2), 4),
            "f05_score": round(float(f_05), 4),
            "fpr": round(float(fpr_t), 4),
            "tp": tp_t,
            "fp": fp_t,
            "tn": tn_t,
            "fn": fn_t
        }
        threshold_records.append(record)
        
        if p >= 0.97 and f_2 > best_tau_f2:
            best_tau_f2 = f_2
            best_tau = tau
            
    print(f"  -> Optimal Threshold on Validation (tau*): {best_tau:.3f} | Val F2: {best_tau_f2:.4f}")
    
    # 6. Single-Pass Final Evaluation on Held-Out Test Set
    print("\n[5/5] Performing Final Evaluation on Held-Out TEST Set (Untouched)...", flush=True)
    print(f"{'Model':<25} | {'Test Acc':<8} | {'Test Prec':<9} | {'Test Rec':<8} | {'Test F1':<7} | {'Test F2':<7} | {'ROC-AUC':<7} | {'PR-AUC':<7} | {'FP':<5} | {'FN':<5}")
    print("-" * 115)
    
    for name, model in models.items():
        if hasattr(model, "predict_proba"):
            test_probs = model.predict_proba(X_test_combined)[:, 1]
        elif hasattr(model, "decision_function"):
            df_scores = model.decision_function(X_test_combined)
            test_probs = (df_scores - df_scores.min()) / (df_scores.max() - df_scores.min() + 1e-8)
        else:
            test_probs = model.predict(X_test_combined).astype(float)
        test_probabilities[name] = test_probs
        
        test_preds = (test_probs >= 0.50).astype(int)
        
        acc = accuracy_score(y_test, test_preds)
        prec = precision_score(y_test, test_preds, zero_division=0)
        rec = recall_score(y_test, test_preds, zero_division=0)
        f1 = f1_score(y_test, test_preds, zero_division=0)
        f2 = fbeta_score(y_test, test_preds, beta=2, zero_division=0)
        auc = roc_auc_score(y_test, test_probs)
        prauc = average_precision_score(y_test, test_probs)
        brier = brier_score_loss(y_test, test_probs)
        cm = confusion_matrix(y_test, test_preds)
        
        tn, fp, fn, tp = int(cm[0, 0]), int(cm[0, 1]), int(cm[1, 0]), int(cm[1, 1])
        test_confusion_matrices[name] = {"tn": tn, "fp": fp, "fn": fn, "tp": tp}
        
        test_benchmark_results[name] = {
            "accuracy": round(float(acc), 4),
            "precision": round(float(prec), 4),
            "recall": round(float(rec), 4),
            "f1_score": round(float(f1), 4),
            "f2_score": round(float(f2), 4),
            "roc_auc": round(float(auc), 4),
            "pr_auc": round(float(prauc), 4),
            "brier_score": round(float(brier), 4),
            "fp": fp,
            "fn": fn,
            "tp": tp,
            "tn": tn
        }
        print(f"{name:<25} | {acc:8.4f} | {prec:9.4f} | {rec:8.4f} | {f1:7.4f} | {f2:7.4f} | {auc:7.4f} | {prauc:7.4f} | {fp:5d} | {fn:5d}")
        
    cand_test_probs = test_probabilities[best_candidate_name]
    opt_test_preds = (cand_test_probs >= best_tau).astype(int)
    opt_test_acc = accuracy_score(y_test, opt_test_preds)
    opt_test_prec = precision_score(y_test, opt_test_preds, zero_division=0)
    opt_test_rec = recall_score(y_test, opt_test_preds, zero_division=0)
    opt_test_f1 = f1_score(y_test, opt_test_preds, zero_division=0)
    opt_test_f2 = fbeta_score(y_test, opt_test_preds, beta=2, zero_division=0)
    cm_opt = confusion_matrix(y_test, opt_test_preds)
    tn_opt, fp_opt, fn_opt, tp_opt = int(cm_opt[0, 0]), int(cm_opt[0, 1]), int(cm_opt[1, 0]), int(cm_opt[1, 1])
    
    print(f"\n>> {best_candidate_name} with Optimal Threshold (tau={best_tau:.3f}) on TEST SET:")
    print(f"   Accuracy: {opt_test_acc:.4f} | Precision: {opt_test_prec:.4f} | Recall: {opt_test_rec:.4f} | F1: {opt_test_f1:.4f} | F2: {opt_test_f2:.4f}")
    print(f"   Confusion Matrix: TP={tp_opt:,}, FP={fp_opt:,}, TN={tn_opt:,}, FN={fn_opt:,}")

    # 7. Comprehensive Error Analysis on Validation & Test
    print("\n--- EXTRACTING REPRESENTATIVE ERROR ANALYSIS EXAMPLES ---", flush=True)
    val_cand_preds = (val_probabilities[best_candidate_name] >= 0.50).astype(int)
    
    val_fp_indices = np.where((val_cand_preds == 1) & (y_val == 0))[0]
    val_fn_indices = np.where((val_cand_preds == 0) & (y_val == 1))[0]
    val_tp_indices = np.where((val_cand_preds == 1) & (y_val == 1))[0]
    val_tn_indices = np.where((val_cand_preds == 0) & (y_val == 0))[0]
    
    def extract_examples(indices, raw_df, probs, max_n=6):
        examples = []
        for idx in indices[:max_n]:
            row = raw_df.iloc[idx]
            examples.append({
                "index": int(idx),
                "source": str(row.get("source", "")),
                "sub_source": str(row.get("sub_source", "")),
                "label_name": str(row.get("label_name", "")),
                "true_label": int(row.get("label", 0)),
                "predicted_prob": round(float(probs[idx]), 4),
                "snippet": str(row.get("text", ""))[:400]
            })
        return examples
        
    error_analysis = {
        "selected_model": best_candidate_name,
        "optimal_threshold": round(float(best_tau), 3),
        "validation_error_counts": {
            "false_positives": len(val_fp_indices),
            "false_negatives": len(val_fn_indices),
            "true_positives": len(val_tp_indices),
            "true_negatives": len(val_tn_indices)
        },
        "sample_false_positives": extract_examples(val_fp_indices, val_df, val_probabilities[best_candidate_name], 6),
        "sample_false_negatives": extract_examples(val_fn_indices, val_df, val_probabilities[best_candidate_name], 6),
        "sample_true_positives": extract_examples(val_tp_indices, val_df, val_probabilities[best_candidate_name], 4),
        "sample_true_negatives": extract_examples(val_tn_indices, val_df, val_probabilities[best_candidate_name], 4)
    }
    
    with open("models/error_analysis.json", "w", encoding="utf-8") as f:
        json.dump(error_analysis, f, indent=2)
    print("  -> Saved error analysis samples to models/error_analysis.json", flush=True)

    # 8. Serialize Artifacts
    print("\n--- SERIALIZING TRAINED MODELS & BENCHMARK ARTIFACTS ---", flush=True)
    joblib.dump(trained_models, "models/trained_models.joblib", compress=3)
    joblib.dump(word_vec, "models/word_vectorizer.joblib", compress=3)
    joblib.dump(char_vec, "models/char_vectorizer.joblib", compress=3)
    joblib.dump(sec_extractor, "models/security_extractor.joblib", compress=3)
    
    benchmark_payload = {
        "dataset_metadata": {
            "train_samples": len(X_train_raw),
            "val_samples": len(X_val_raw),
            "test_samples": len(X_test_raw),
            "total_samples": len(X_train_raw) + len(X_val_raw) + len(X_test_raw),
            "feature_dimension": int(X_train_combined.shape[1]),
            "threat_ratio_val": round(float(np.mean(y_val)), 4),
            "threat_ratio_test": round(float(np.mean(y_test)), 4)
        },
        "validation_metrics": val_benchmark_results,
        "test_metrics": test_benchmark_results,
        "metrics": val_benchmark_results,
        "models": val_benchmark_results,
        "selected_model": best_candidate_name,
        "optimal_threshold": round(float(best_tau), 3),
        "optimal_test_metrics": {
            "accuracy": round(float(opt_test_acc), 4),
            "precision": round(float(opt_test_prec), 4),
            "recall": round(float(opt_test_rec), 4),
            "f1_score": round(float(opt_test_f1), 4),
            "f2_score": round(float(opt_test_f2), 4),
            "confusion_matrix": {"tp": tp_opt, "fp": fp_opt, "tn": tn_opt, "fn": fn_opt}
        },
        "threshold_sweep": threshold_records,
        "roc_curves": roc_curves,
        "pr_curves": pr_curves,
        "confusion_matrices": val_confusion_matrices,
        "test_confusion_matrices": test_confusion_matrices,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    with open("models/benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump(benchmark_payload, f, indent=2)
        
    print("\n[SUCCESS] ALL 8 MODELS TRAINED, VALIDATED, THRESHOLD-OPTIMIZED, AND EVALUATED ON TEST SET!")
    print("=" * 70, flush=True)


if __name__ == "__main__":
    train_and_benchmark_all()
