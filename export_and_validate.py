import os
import sys
import json
import pandas as pd
import numpy as np

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def validate_and_create_splits():
    df = pd.read_parquet('smolified_fakejob_expanded.parquet')
    print("=== DATASET VALIDATION REPORT ===")
    print(f"Total Records: {len(df)}")
    print(f"Columns: {df.columns.tolist()}")
    
    null_counts = df.isnull().sum().to_dict()
    print(f"Null Values per column: {null_counts}")
    assert sum(null_counts.values()) == 0, "Null values found!"
    
    duplicate_users = df.duplicated(subset=['user']).sum()
    print(f"Duplicate 'user' prompts: {duplicate_users}")
    assert duplicate_users == 0, "Duplicate prompts found!"
    
    invalid_assistant = df[~df['assistant'].str.startswith(('Classification: Fake.', 'Classification: Real.'))]
    print(f"Invalid 'assistant' outputs: {len(invalid_assistant)}")
    assert len(invalid_assistant) == 0, "Invalid assistant classification format!"
    
    fake_mask = df['assistant'].str.startswith('Classification: Fake.')
    real_mask = df['assistant'].str.startswith('Classification: Real.')
    fake_count = fake_mask.sum()
    real_count = real_mask.sum()
    print(f"Fake Jobs: {fake_count} ({fake_count/len(df)*100:.2f}%)")
    print(f"Real Jobs: {real_count} ({real_count/len(df)*100:.2f}%)")
    
    user_len = df['user'].str.len()
    asst_len = df['assistant'].str.len()
    
    stats = {
        "total_records": len(df),
        "fake_records": int(fake_count),
        "real_records": int(real_count),
        "fake_percentage": round(float(fake_count/len(df)*100), 2),
        "real_percentage": round(float(real_count/len(df)*100), 2),
        "user_length_chars": {
            "min": int(user_len.min()),
            "mean": round(float(user_len.mean()), 1),
            "median": int(user_len.median()),
            "max": int(user_len.max())
        },
        "assistant_length_chars": {
            "min": int(asst_len.min()),
            "mean": round(float(asst_len.mean()), 1),
            "median": int(asst_len.median()),
            "max": int(asst_len.max())
        },
        "columns": df.columns.tolist(),
        "formats_available": [
            "smolified_fakejob_expanded.parquet",
            "smolified_fakejob_expanded.jsonl",
            "smolified_fakejob_expanded.csv",
            "splits/train.parquet",
            "splits/validation.parquet",
            "splits/test.parquet"
        ]
    }
    
    with open('dataset_summary.json', 'w') as f:
        json.dump(stats, f, indent=2)
    print("\nSaved summary to dataset_summary.json")
    
    import os
    os.makedirs('splits', exist_ok=True)
    
    df['label'] = np.where(df['assistant'].str.startswith('Classification: Fake.'), 'fake', 'real')
    
    train_dfs, val_dfs, test_dfs = [], [], []
    for label, group in df.groupby('label'):
        shuffled = group.sample(frac=1.0, random_state=42).reset_index(drop=True)
        n = len(shuffled)
        n_train = int(0.8 * n)
        n_val = int(0.1 * n)
        
        train_dfs.append(shuffled.iloc[:n_train])
        val_dfs.append(shuffled.iloc[n_train:n_train+n_val])
        test_dfs.append(shuffled.iloc[n_train+n_val:])
        
    train_df = pd.concat(train_dfs).sample(frac=1.0, random_state=42).drop(columns=['label']).reset_index(drop=True)
    val_df = pd.concat(val_dfs).sample(frac=1.0, random_state=42).drop(columns=['label']).reset_index(drop=True)
    test_df = pd.concat(test_dfs).sample(frac=1.0, random_state=42).drop(columns=['label']).reset_index(drop=True)
    
    train_df.to_parquet('splits/train.parquet', index=False)
    train_df.to_json('splits/train.jsonl', orient='records', lines=True)
    
    val_df.to_parquet('splits/validation.parquet', index=False)
    val_df.to_json('splits/validation.jsonl', orient='records', lines=True)
    
    test_df.to_parquet('splits/test.parquet', index=False)
    test_df.to_json('splits/test.jsonl', orient='records', lines=True)
    
    print(f"\nSplits successfully created:")
    print(f"  - Train: {len(train_df)} rows ({len(train_df)/len(df)*100:.1f}%)")
    print(f"  - Validation: {len(val_df)} rows ({len(val_df)/len(df)*100:.1f}%)")
    print(f"  - Test: {len(test_df)} rows ({len(test_df)/len(df)*100:.1f}%)")
    
    print("\nSample Inspection (3 Fake, 3 Real):")
    for idx, row in df[df['assistant'].str.startswith('Classification: Fake.')].head(3).iterrows():
        print(f"\n[FAKE EXAMPLE {idx}]")
        print("User:", row['user'])
        print("Assistant:", row['assistant'])
        
    for idx, row in df[df['assistant'].str.startswith('Classification: Real.')].head(3).iterrows():
        print(f"\n[REAL EXAMPLE {idx}]")
        print("User:", row['user'])
        print("Assistant:", row['assistant'])

if __name__ == '__main__':
    validate_and_create_splits()
