# Master Dataset Integration & Quality Audit Report

**Generated Date**: 2026-09-16  
**Artifact**: `data/processed/master_dataset.parquet`  
**Total Records (Post-Deduplication)**: **111,510**

---

## 1. Executive Summary

This audit report documents the multi-source dataset integration pipeline combining **4 distinct data sources** into a unified, high-integrity schema for fake job and cyber threat detection:

1. **`indian_job_scam`**: Verified Indian fake internship, job scam, and corporate job postings.
2. **`fake_job_emscad`**: Employment Scam Aegean Dataset (EMSCAD) containing global job postings.
3. **`phishing_email`**: Consolidated collection of phishing and legitimate emails (CEAS_08, Enron, Ling, Nazario, Nigerian Fraud, SpamAssasin).
4. **`spam_promotional`**: Email safety triage and prompt-attack/promotional spam dataset.

---

## 2. Dataset Ingestion & Row Counts

| Source Identifier | Raw Files Ingested | Rows Before Merge | Rows After Deduplication | Duplicates Removed |
| :--- | :--- | :---: | :---: | :---: |
| **`indian_job_scam`** | `smolified_fakejob_expanded.jsonl` | 3,200 | 3,200 | 0 |
| **`fake_job_emscad`** | `job_postings_train.csv`, `job_postings_test.csv` | 17,599 | 15,921 | 1,678 |
| **`phishing_email`** | `CEAS_08.csv`, `Enron.csv`, `Ling.csv`, `Nazario.csv`, `Nigerian_Fraud.csv`, `SpamAssasin.csv` | 82,486 | 82,391 | 95 |
| **`spam_promotional`** | `email_safety_triage_10k.jsonl` | 10,000 | 9,998 | 2 |
| **TOTAL** | **10 Raw Files** | **113,285** | **111,510** | **1,775** |

---

## 3. Schema & Available Columns

The normalized dataset follows a strict 8-column schema:

| Column Name | Data Type | Missing Count | Description |
| :--- | :--- | :---: | :--- |
| `id` | `int64` | 0 | Unique sequential integer record identifier (1 to 111,510). |
| `text` | `string` | 0 | Pristine text content of the job posting or email (prompt instructions stripped). |
| `label` | `float64` / `int64` | 4899 | Normalized binary classification (`1` = Scam/Fake/Phishing/Threat, `0` = Real/Legitimate/Safe, `NaN` = Unlabelled test records). |
| `label_name` | `string` | 0 | Descriptive normalized label (`fake`, `real`, `phishing`, `legitimate`, `safe`, `spam`, `prompt_attack`, `suspicious`, `unlabelled`). |
| `original_label` | `string` | 0 | Exact raw label preserved from original source without alteration. |
| `source` | `string` | 0 | Top-level source category (`indian_job_scam`, `fake_job_emscad`, `phishing_email`, `spam_promotional`). |
| `sub_source` | `string` | 0 | Specific sub-dataset or file identifier. |
| `metadata` | `string (JSON)` | 0 | JSON-serialized dictionary of domain-specific fields (e.g. sender, location, salary range, triage reasoning). |

---

## 4. Label Mapping Breakdown by Source

### 4.1. `indian_job_scam`
- **Original Source Format**: Assistant field in JSONL (`Classification: Fake` vs `Classification: Real`).
- **Original Label Distribution**:
  - `Fake`: 1,934
  - `Real`: 1,266
- **Normalized Mapping**:
  - `Fake` → `label = 1` (`label_name = 'fake'`)
  - `Real` → `label = 0` (`label_name = 'real'`)

### 4.2. `fake_job_emscad`
- **Original Source Format**: `fraudulent` column in `job_postings_train.csv` and unlabelled in `job_postings_test.csv`.
- **Original Label Distribution**:
  - `0` (Real): 11,411
  - `1` (Fraudulent): 589
  - `None (unlabelled)`: 5,599
- **Normalized Mapping**:
  - `1` → `label = 1` (`label_name = 'fake'`)
  - `0` → `label = 0` (`label_name = 'real'`)
  - Unlabelled → `label = NaN` (`label_name = 'unlabelled'`)

### 4.3. `phishing_email`
- **Original Source Format**: Binary `label` column across 6 sub-corpora.
- **Original Label Distribution**:
  - `1` (Phishing/Spam): 42,891
  - `0` (Legitimate/Ham): 39,595
- **Sub-Corpora Composition**:
  - `CEAS_08`: 39,154 records
  - `Enron`: 29,767 records
  - `SpamAssasin`: 5,809 records
  - `Nigerian_Fraud`: 3,332 records
  - `Ling`: 2,859 records
  - `Nazario`: 1,565 records
- **Normalized Mapping**:
  - `1` → `label = 1` (`label_name = 'phishing'`)
  - `0` → `label = 0` (`label_name = 'legitimate'`)

### 4.4. `spam_promotional`
- **Original Source Format**: Structured JSON `output` object with `risk`, `triage`, `priority`, and `should_process`.
- **Original Label Distribution by Risk**:
  - `risk:none` (Safe): 4,843
  - `risk:phishing`: 2,102
  - `risk:prompt_attack`: 1,763
  - `risk:spam`: 997
  - `risk:suspicious`: 295
- **Normalized Mapping**:
  - `risk:none` & `should_process:True` → `label = 0` (`label_name = 'safe'`)
  - `risk:phishing` → `label = 1` (`label_name = 'phishing'`)
  - `risk:prompt_attack` → `label = 1` (`label_name = 'prompt_attack'`)
  - `risk:spam` → `label = 1` (`label_name = 'spam'`)
  - `risk:suspicious` → `label = 1` (`label_name = 'suspicious'`)

---

## 5. Text Length & Corpus Statistics

### 5.1. Overall Text Statistics (Post-Deduplication)

| Metric | Character Count | Word Count |
| :--- | :---: | :---: |
| **Minimum** | 13 | 2 |
| **Maximum** | 4,599,704 | 127,128 |
| **Mean** | 1,796.09 | 272.42 |
| **Median** | 853.0 | 145.0 |
| **Standard Deviation** | 14,591.03 | 703.4 |

### 5.2. Source-Wise Text Length Comparison

| Source Identifier | Record Count | Mean Chars | Median Chars | Mean Words | Median Words |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **`indian_job_scam`** | 3,200 | 231.4 | 215.0 | 32.3 | 28.0 |
| **`fake_job_emscad`** | 15,921 | 2,784.9 | 2,623.0 | 391.4 | 365.0 |
| **`phishing_email`** | 82,391 | 1,806.4 | 785.0 | 280.4 | 138.0 |
| **`spam_promotional`** | 9,998 | 637.3 | 439.0 | 94.0 | 70.0 |

---

## 6. Data Integrity & Deduplication Verification

1. **Exact Deduplication**: Exactly **1,775 duplicate records** across sources were identified and pruned, preserving the first occurrence.
2. **Text Purity**: The `assistant` field explanations from `indian_job_scam` and system prompt headers from `spam_promotional` were excluded from the `text` field, ensuring the NLP model learns strictly from authentic content.
3. **Zero Label Invention**: Unlabelled EMSCAD test records have their original state preserved (`label = NaN`, `original_label = 'None (unlabelled)'`).
4. **Source Traceability**: Every record contains an immutable `source` tag, `sub_source` origin, and full `metadata` JSON blob.

---
