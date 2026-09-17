import os
import sys
import pandas as pd
import numpy as np

def test_dataset_partitions():
    assert os.path.exists("splits/train.parquet"), "train.parquet missing"
    assert os.path.exists("splits/validation.parquet"), "validation.parquet missing"
    assert os.path.exists("splits/test.parquet"), "test.parquet missing"
    assert os.path.exists("data/processed/master_dataset.parquet"), "master_dataset.parquet missing"

    df_tr = pd.read_parquet("splits/train.parquet")
    df_va = pd.read_parquet("splits/validation.parquet")
    df_te = pd.read_parquet("splits/test.parquet")
    df_master = pd.read_parquet("data/processed/master_dataset.parquet")

    assert len(df_tr) == 74627, f"Expected 74,627 train records, got {len(df_tr)}"
    assert len(df_va) == 15992, f"Expected 15,992 val records, got {len(df_va)}"
    assert len(df_te) == 15992, f"Expected 15,992 test records, got {len(df_te)}"
    assert len(df_master) == 111510, f"Expected 111,510 master records, got {len(df_master)}"
    print("  [PASS] Dataset Partition & Record Count Test")

def test_leakage_checks():
    df_tr = pd.read_parquet("splits/train.parquet")
    df_va = pd.read_parquet("splits/validation.parquet")
    df_te = pd.read_parquet("splits/test.parquet")

    set_tr_id = set(df_tr["id"])
    set_va_id = set(df_va["id"])
    set_te_id = set(df_te["id"])

    assert len(set_tr_id.intersection(set_va_id)) == 0, "Leakage detected between Train and Val IDs"
    assert len(set_tr_id.intersection(set_te_id)) == 0, "Leakage detected between Train and Test IDs"
    assert len(set_va_id.intersection(set_te_id)) == 0, "Leakage detected between Val and Test IDs"

    set_tr_text = set(df_tr["text"])
    set_va_text = set(df_va["text"])
    set_te_text = set(df_te["text"])

    assert len(set_tr_text.intersection(set_va_text)) == 0, "Text leakage detected between Train and Val"
    assert len(set_tr_text.intersection(set_te_text)) == 0, "Text leakage detected between Train and Test"
    assert len(set_va_text.intersection(set_te_text)) == 0, "Text leakage detected between Val and Test"
    print("  [PASS] Zero Data/Text Leakage Test")

if __name__ == "__main__":
    print("RUNNING DATA INTEGRITY TESTS")
    test_dataset_partitions()
    test_leakage_checks()
    print("ALL DATA INTEGRITY TESTS PASSED.")
