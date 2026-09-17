import os
import json
import sys
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split

sys.stdout.reconfigure(encoding='utf-8')

print("=" * 70)
print("CREATING LEAK-FREE STRATIFIED TRAIN / VALIDATION / TEST SPLITS")
print("=" * 70)

os.makedirs("splits", exist_ok=True)

master_parquet = "data/processed/master_dataset.parquet"
df = pd.read_parquet(master_parquet)
print(f"Loaded master dataset: {len(df):,} total records")

# 1. Separate Unlabelled Data
unlabelled_mask = df["label"].isna()
df_unlabelled = df[unlabelled_mask].copy().reset_index(drop=True)
df_labeled = df[~unlabelled_mask].copy().reset_index(drop=True)

print(f"  -> Labeled records   : {len(df_labeled):,}")
print(f"  -> Unlabelled records : {len(df_unlabelled):,}")

# Save unlabelled holdout
unlabelled_path = "splits/unlabelled_holdout.parquet"
df_unlabelled.to_parquet(unlabelled_path, index=False, engine="pyarrow")
print(f"  -> Saved unlabelled holdout to: {unlabelled_path}")

# 2. Multi-Key Stratification Key
df_labeled["strat_key"] = df_labeled["source"].astype(str) + "_" + df_labeled["label_name"].astype(str)
strat_counts = df_labeled["strat_key"].value_counts()
print("\nStratification Key Distribution:")
for k, v in strat_counts.items():
    print(f"  {k:45s}: {v:6,d} records")

# Handle rare classes with < 3 samples if any
rare_keys = strat_counts[strat_counts < 3].index.tolist()
if rare_keys:
    print(f"\nWarning: Found rare stratification keys: {rare_keys}")
    df_labeled["strat_key"] = df_labeled["strat_key"].apply(lambda k: "other_rare" if k in rare_keys else k)

# 3. Perform 70% Train, 15% Validation, 15% Test Split
# Step A: 70% Train, 30% Temp (Val + Test)
train_df, temp_df = train_test_split(
    df_labeled,
    test_size=0.30,
    random_state=42,
    stratify=df_labeled["strat_key"]
)

# Step B: 50% / 50% of the 30% temp into Val (15%) and Test (15%)
val_df, test_df = train_test_split(
    temp_df,
    test_size=0.50,
    random_state=42,
    stratify=temp_df["strat_key"]
)

# Clean up strat_key before saving
train_df = train_df.drop(columns=["strat_key"]).reset_index(drop=True)
val_df = val_df.drop(columns=["strat_key"]).reset_index(drop=True)
test_df = test_df.drop(columns=["strat_key"]).reset_index(drop=True)

print("\n" + "=" * 70)
print("SPLIT SIZE SUMMARY")
print("=" * 70)
print(f"Train set      : {len(train_df):6,d} samples ({len(train_df)/len(df_labeled)*100:.2f}%)")
print(f"Validation set : {len(val_df):6,d} samples ({len(val_df)/len(df_labeled)*100:.2f}%)")
print(f"Test set       : {len(test_df):6,d} samples ({len(test_df)/len(df_labeled)*100:.2f}%)")

# 4. Zero Data Leakage Verification
train_texts = set(train_df["text"])
val_texts = set(val_df["text"])
test_texts = set(test_df["text"])

train_val_overlap = len(train_texts.intersection(val_texts))
train_test_overlap = len(train_texts.intersection(test_texts))
val_test_overlap = len(val_texts.intersection(test_texts))

print("\n" + "=" * 70)
print("DATA LEAKAGE VERIFICATION")
print("=" * 70)
print(f"Train <-> Val Overlap  : {train_val_overlap} (Expected: 0)")
print(f"Train <-> Test Overlap : {train_test_overlap} (Expected: 0)")
print(f"Val <-> Test Overlap   : {val_test_overlap} (Expected: 0)")
assert train_val_overlap == 0 and train_test_overlap == 0 and val_test_overlap == 0, "CRITICAL ERROR: Data leakage detected across splits!"
print("[VERIFIED] ZERO text overlap across Train, Validation, and Test splits.")

# 5. Save Parquet Files
train_path = "splits/train.parquet"
val_path = "splits/validation.parquet"
test_path = "splits/test.parquet"

train_df.to_parquet(train_path, index=False, engine="pyarrow")
val_df.to_parquet(val_path, index=False, engine="pyarrow")
test_df.to_parquet(test_path, index=False, engine="pyarrow")

# 6. Save Split Summary JSON
summary = {
    "total_master_records": len(df),
    "total_labeled_records": len(df_labeled),
    "total_unlabelled_records": len(df_unlabelled),
    "splits": {
        "train": {
            "samples": len(train_df),
            "threat_count": int((train_df["label"] == 1.0).sum()),
            "safe_count": int((train_df["label"] == 0.0).sum()),
            "threat_percentage": round(float((train_df["label"] == 1.0).mean() * 100), 2),
            "sources": train_df["source"].value_counts().to_dict(),
            "label_names": train_df["label_name"].value_counts().to_dict()
        },
        "validation": {
            "samples": len(val_df),
            "threat_count": int((val_df["label"] == 1.0).sum()),
            "safe_count": int((val_df["label"] == 0.0).sum()),
            "threat_percentage": round(float((val_df["label"] == 1.0).mean() * 100), 2),
            "sources": val_df["source"].value_counts().to_dict(),
            "label_names": val_df["label_name"].value_counts().to_dict()
        },
        "test": {
            "samples": len(test_df),
            "threat_count": int((test_df["label"] == 1.0).sum()),
            "safe_count": int((test_df["label"] == 0.0).sum()),
            "threat_percentage": round(float((test_df["label"] == 1.0).mean() * 100), 2),
            "sources": test_df["source"].value_counts().to_dict(),
            "label_names": test_df["label_name"].value_counts().to_dict()
        },
        "unlabelled_holdout": {
            "samples": len(df_unlabelled),
            "source": "fake_job_emscad"
        }
    }
}

with open("splits/split_summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)

print("\n[SUCCESS] Stratified splits exported to splits/ directory.")
print("=" * 70)
