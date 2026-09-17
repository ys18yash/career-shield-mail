import os
import json
import glob
import sys
import re
import pandas as pd
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

os.makedirs("data/processed", exist_ok=True)
os.makedirs("reports", exist_ok=True)

def clean_str(val):
    if val is None or pd.isna(val):
        return ""
    s = str(val).strip()
    return "" if s.lower() == "nan" else s

def run_pipeline():
    print("=" * 70)
    print("STARTING DATASET NORMALIZATION & INTEGRATION PIPELINE")
    print("=" * 70)

    all_records = []
    audit_data = {
        "sources": {},
        "total_rows_before_merge": 0,
        "total_rows_after_merge": 0,
        "duplicates_removed": 0
    }

    # 1. INDIAN JOB SCAM
    ind_path = "data/raw/indian_job_scam/smolified_fakejob_expanded.jsonl"
    ind_count = 0
    ind_orig_labels = {}
    ind_norm_labels = {}

    with open(ind_path, "r", encoding="utf-8") as f:
        for line in f:
            data = json.loads(line)
            user_text = clean_str(data.get("user", ""))
            asst_text = clean_str(data.get("assistant", ""))
            
            if "Classification: Fake" in asst_text:
                orig_lbl = "Fake"
                norm_lbl = 1
                lbl_name = "fake"
            elif "Classification: Real" in asst_text:
                orig_lbl = "Real"
                norm_lbl = 0
                lbl_name = "real"
            else:
                orig_lbl = asst_text
                norm_lbl = None
                lbl_name = "unknown"
                
            ind_orig_labels[orig_lbl] = ind_orig_labels.get(orig_lbl, 0) + 1
            ind_norm_labels[lbl_name] = ind_norm_labels.get(lbl_name, 0) + 1
            ind_count += 1
            
            meta = {
                "system_prompt": clean_str(data.get("system")),
                "original_file": "smolified_fakejob_expanded.jsonl"
            }
            
            all_records.append({
                "text": user_text,
                "label": norm_lbl,
                "label_name": lbl_name,
                "original_label": orig_lbl,
                "source": "indian_job_scam",
                "sub_source": "smolified_fakejob_expanded",
                "metadata": json.dumps(meta, ensure_ascii=False)
            })

    audit_data["sources"]["indian_job_scam"] = {
        "files": ["smolified_fakejob_expanded.jsonl"],
        "row_count": ind_count,
        "original_labels": ind_orig_labels,
        "normalized_labels": ind_norm_labels
    }

    # 2. EMSCAD FAKE JOB
    emscad_count = 0
    emscad_orig_labels = {}
    emscad_norm_labels = {}
    emscad_files = []

    train_csv = "data/raw/fake_job_emscad/job_postings_train.csv"
    if os.path.exists(train_csv):
        emscad_files.append("job_postings_train.csv")
        df_tr = pd.read_csv(train_csv)
        for _, row in df_tr.iterrows():
            text_parts = []
            for field in ["title", "company_profile", "description", "requirements", "benefits"]:
                val = clean_str(row.get(field))
                if val:
                    text_parts.append(val)
            full_text = "\n\n".join(text_parts).strip()
            
            orig_lbl = row.get("fraudulent")
            norm_lbl = int(orig_lbl) if pd.notna(orig_lbl) else None
            lbl_name = "fake" if norm_lbl == 1 else ("real" if norm_lbl == 0 else "unknown")
            
            orig_str = str(orig_lbl)
            emscad_orig_labels[orig_str] = emscad_orig_labels.get(orig_str, 0) + 1
            emscad_norm_labels[lbl_name] = emscad_norm_labels.get(lbl_name, 0) + 1
            emscad_count += 1
            
            meta = {
                "id": row.get("id"),
                "location": clean_str(row.get("location")),
                "department": clean_str(row.get("department")),
                "salary_range": clean_str(row.get("salary_range")),
                "telecommuting": row.get("telecommuting"),
                "has_company_logo": row.get("has_company_logo"),
                "has_questions": row.get("has_questions"),
                "employment_type": clean_str(row.get("employment_type")),
                "required_experience": clean_str(row.get("required_experience")),
                "required_education": clean_str(row.get("required_education")),
                "industry": clean_str(row.get("industry")),
                "function": clean_str(row.get("function"))
            }
            
            all_records.append({
                "text": full_text,
                "label": norm_lbl,
                "label_name": lbl_name,
                "original_label": orig_str,
                "source": "fake_job_emscad",
                "sub_source": "job_postings_train",
                "metadata": json.dumps(meta, ensure_ascii=False)
            })

    test_csv = "data/raw/fake_job_emscad/job_postings_test.csv"
    if os.path.exists(test_csv):
        emscad_files.append("job_postings_test.csv")
        df_te = pd.read_csv(test_csv)
        for _, row in df_te.iterrows():
            text_parts = []
            for field in ["title", "company_profile", "description", "requirements", "benefits"]:
                val = clean_str(row.get(field))
                if val:
                    text_parts.append(val)
            full_text = "\n\n".join(text_parts).strip()
            
            orig_str = "None (unlabelled)"
            lbl_name = "unlabelled"
            emscad_orig_labels[orig_str] = emscad_orig_labels.get(orig_str, 0) + 1
            emscad_norm_labels[lbl_name] = emscad_norm_labels.get(lbl_name, 0) + 1
            emscad_count += 1
            
            meta = {
                "id": row.get("id"),
                "location": clean_str(row.get("location")),
                "department": clean_str(row.get("department")),
                "salary_range": clean_str(row.get("salary_range")),
                "telecommuting": row.get("telecommuting"),
                "has_company_logo": row.get("has_company_logo"),
                "has_questions": row.get("has_questions"),
                "employment_type": clean_str(row.get("employment_type")),
                "required_experience": clean_str(row.get("required_experience")),
                "required_education": clean_str(row.get("required_education")),
                "industry": clean_str(row.get("industry")),
                "function": clean_str(row.get("function"))
            }
            
            all_records.append({
                "text": full_text,
                "label": None,
                "label_name": lbl_name,
                "original_label": orig_str,
                "source": "fake_job_emscad",
                "sub_source": "job_postings_test",
                "metadata": json.dumps(meta, ensure_ascii=False)
            })

    audit_data["sources"]["fake_job_emscad"] = {
        "files": emscad_files,
        "row_count": emscad_count,
        "original_labels": emscad_orig_labels,
        "normalized_labels": emscad_norm_labels
    }

    # 3. PHISHING EMAIL
    phish_count = 0
    phish_orig_labels = {}
    phish_norm_labels = {}
    phish_files = ["CEAS_08.csv", "Enron.csv", "Ling.csv", "Nazario.csv", "Nigerian_Fraud.csv", "SpamAssasin.csv"]

    for csv_name in phish_files:
        p = os.path.join("data/raw/phishing_email", csv_name)
        if os.path.exists(p):
            df_p = pd.read_csv(p)
            sub_name = csv_name.replace(".csv", "")
            for _, row in df_p.iterrows():
                subj = clean_str(row.get("subject"))
                body = clean_str(row.get("body"))
                
                if subj and body:
                    full_text = f"Subject: {subj}\n\n{body}"
                elif subj:
                    full_text = f"Subject: {subj}"
                elif body:
                    full_text = body
                else:
                    full_text = ""
                    
                orig_lbl = row.get("label")
                norm_lbl = int(orig_lbl) if pd.notna(orig_lbl) else None
                lbl_name = "phishing" if norm_lbl == 1 else ("legitimate" if norm_lbl == 0 else "unknown")
                
                orig_str = str(orig_lbl)
                phish_orig_labels[orig_str] = phish_orig_labels.get(orig_str, 0) + 1
                phish_norm_labels[lbl_name] = phish_norm_labels.get(lbl_name, 0) + 1
                phish_count += 1
                
                meta = {
                    "sender": clean_str(row.get("sender")),
                    "receiver": clean_str(row.get("receiver")),
                    "date": clean_str(row.get("date")),
                    "urls": clean_str(row.get("urls")),
                    "sub_source_file": csv_name
                }
                
                all_records.append({
                    "text": full_text,
                    "label": norm_lbl,
                    "label_name": lbl_name,
                    "original_label": orig_str,
                    "source": "phishing_email",
                    "sub_source": sub_name,
                    "metadata": json.dumps(meta, ensure_ascii=False)
                })

    audit_data["sources"]["phishing_email"] = {
        "files": phish_files,
        "row_count": phish_count,
        "original_labels": phish_orig_labels,
        "normalized_labels": phish_norm_labels
    }

    # 4. SPAM PROMOTIONAL
    spam_count = 0
    spam_orig_labels = {}
    spam_norm_labels = {}
    spam_p = "data/raw/spam_promotional/email_safety_triage_10k.jsonl"
    inst_prefix = "Classify the following content for email triage and prompt-attack filtering. Return only strict JSON with keys triage, priority, risk, should_process, confidence, and reason.\n\n"

    with open(spam_p, "r", encoding="utf-8") as f:
        for line in f:
            data = json.loads(line)
            raw_inp = clean_str(data.get("input", ""))
            
            if raw_inp.startswith(inst_prefix):
                email_text = raw_inp[len(inst_prefix):].strip()
            elif "\n\n" in raw_inp:
                email_text = raw_inp.split("\n\n", 1)[1].strip()
            else:
                email_text = raw_inp
                
            raw_out = data.get("output", "{}")
            out_dict = json.loads(raw_out) if isinstance(raw_out, str) else raw_out
            
            risk = out_dict.get("risk", "none")
            triage = out_dict.get("triage", "review")
            should_proc = out_dict.get("should_process", True)
            
            if risk in ["phishing", "prompt_attack", "spam", "suspicious"] or not should_proc:
                norm_lbl = 1
                lbl_name = risk if risk != "none" else "threat"
            elif risk == "none" and should_proc:
                norm_lbl = 0
                lbl_name = "safe"
            else:
                norm_lbl = None
                lbl_name = "unknown"
                
            risk_str = f"risk:{risk}|triage:{triage}|should_process:{should_proc}"
            spam_orig_labels[risk_str] = spam_orig_labels.get(risk_str, 0) + 1
            spam_norm_labels[lbl_name] = spam_norm_labels.get(lbl_name, 0) + 1
            spam_count += 1
            
            all_records.append({
                "text": email_text,
                "label": norm_lbl,
                "label_name": lbl_name,
                "original_label": json.dumps(out_dict, ensure_ascii=False),
                "source": "spam_promotional",
                "sub_source": "email_safety_triage_10k",
                "metadata": json.dumps(out_dict, ensure_ascii=False)
            })

    audit_data["sources"]["spam_promotional"] = {
        "files": ["email_safety_triage_10k.jsonl"],
        "row_count": spam_count,
        "original_labels": spam_orig_labels,
        "normalized_labels": spam_norm_labels
    }

    # MERGE & DEDUPLICATE
    df_all = pd.DataFrame(all_records)
    total_before = len(df_all)
    audit_data["total_rows_before_merge"] = total_before

    dup_mask = df_all.duplicated(subset=["text"], keep="first")
    duplicates_removed = int(dup_mask.sum())
    audit_data["duplicates_removed"] = duplicates_removed

    df_master = df_all[~dup_mask].copy().reset_index(drop=True)
    total_after = len(df_master)
    audit_data["total_rows_after_merge"] = total_after

    df_master["id"] = range(1, len(df_master) + 1)
    ordered_cols = ["id", "text", "label", "label_name", "original_label", "source", "sub_source", "metadata"]
    df_master = df_master[ordered_cols]

    out_parquet = "data/processed/master_dataset.parquet"
    df_master.to_parquet(out_parquet, index=False, engine="pyarrow")
    print(f"Master dataset written to {out_parquet} ({total_after:,} rows)")

if __name__ == "__main__":
    run_pipeline()
