import os
import time
import sqlite3
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict

FEEDBACK_MIN_NEW_LABELS = int(os.environ.get("FEEDBACK_MIN_NEW_LABELS", "500"))
FEEDBACK_MIN_CONTRIBUTING_USERS = int(os.environ.get("FEEDBACK_MIN_CONTRIBUTING_USERS", "3"))
FEEDBACK_MAX_USER_SHARE = float(os.environ.get("FEEDBACK_MAX_USER_SHARE", "0.20"))
FEEDBACK_MAX_SAMPLES_PER_USER = int(os.environ.get("FEEDBACK_MAX_SAMPLES_PER_USER", "250"))
FEEDBACK_RATE_LIMIT_PER_MINUTE = int(os.environ.get("FEEDBACK_RATE_LIMIT_PER_MINUTE", "60"))

_user_submission_timestamps = defaultdict(list)


class FeedbackQualityEngine:
    """Enforces multi-user diversity, anti-poisoning caps, deduplication, and quality gates."""

    @staticmethod
    def check_rate_limit(user_id: str, max_requests: int = FEEDBACK_RATE_LIMIT_PER_MINUTE) -> bool:
        """Enforces a sliding-window rate limit per user to prevent automated abuse."""
        now = time.time()
        window_start = now - 60.0
        
        user_key = (user_id or "anonymous").strip().lower()
        timestamps = _user_submission_timestamps[user_key]
        
        _user_submission_timestamps[user_key] = [t for t in timestamps if t > window_start]
        
        if len(_user_submission_timestamps[user_key]) >= max_requests:
            return False
            
        _user_submission_timestamps[user_key].append(now)
        return True

    @staticmethod
    def assess_global_eligibility(db_path: str) -> Dict[str, Any]:
        """
        Assesses whether accumulated feedback satisfies all multi-user diversity,
        volume, and safety constraints for triggering a candidate retraining cycle.
        """
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT user_id, message_hash, label, text_snippet
                FROM feedback_records
                WHERE is_eligible = 1 AND dataset_version IS NULL AND label IN ('SAFE', 'SPAM')
                ORDER BY updated_at ASC
            ''')
            rows = cursor.fetchall()

        total_eligible = len(rows)
        if total_eligible == 0:
            return {
                "eligible_for_retraining": False,
                "reason": "No un-snapshotted eligible feedback samples found.",
                "total_eligible_samples": 0,
                "contributing_users": 0,
                "safe_count": 0,
                "spam_count": 0,
                "min_required_labels": FEEDBACK_MIN_NEW_LABELS
            }

        user_counts = defaultdict(int)
        label_counts = defaultdict(int)
        unique_hashes = set()

        for user_id, msg_hash, label, _ in rows:
            user_counts[user_id] += 1
            label_counts[label] += 1
            unique_hashes.add(msg_hash)

        contributing_users = len(user_counts)
        safe_count = label_counts["SAFE"]
        spam_count = label_counts["SPAM"]

        failures = []
        if total_eligible < FEEDBACK_MIN_NEW_LABELS:
            failures.append(f"Insufficient eligible labels: {total_eligible}/{FEEDBACK_MIN_NEW_LABELS}")
            
        if contributing_users < FEEDBACK_MIN_CONTRIBUTING_USERS:
            failures.append(f"Insufficient contributing users: {contributing_users}/{FEEDBACK_MIN_CONTRIBUTING_USERS}")

        if safe_count == 0 or spam_count == 0:
            failures.append(f"Lack of bidirectional class diversity (SAFE: {safe_count}, SPAM: {spam_count})")

        is_eligible = len(failures) == 0

        return {
            "eligible_for_retraining": is_eligible,
            "reason": "Passed all multi-user diversity and volume checks." if is_eligible else "; ".join(failures),
            "total_eligible_samples": total_eligible,
            "unique_messages": len(unique_hashes),
            "contributing_users": contributing_users,
            "safe_count": safe_count,
            "spam_count": spam_count,
            "user_distribution": dict(user_counts),
            "min_required_labels": FEEDBACK_MIN_NEW_LABELS
        }

    @staticmethod
    def extract_capped_candidate_samples(db_path: str, max_total_samples: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Extracts verified eligible feedback samples while strictly capping per-user contributions.
        Guarantees that no single tenant can dominate or poison the training batch.
        """
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT feedback_id, user_id, message_hash, label, text_snippet, created_at
                FROM feedback_records
                WHERE is_eligible = 1 AND dataset_version IS NULL AND label IN ('SAFE', 'SPAM')
                ORDER BY created_at ASC
            ''')
            rows = cursor.fetchall()

        if not rows:
            return []

        user_buckets = defaultdict(list)
        for r in rows:
            user_buckets[r[1]].append({
                "feedback_id": r[0],
                "user_id": r[1],
                "message_hash": r[2],
                "label": 1 if r[3] == "SPAM" else 0,
                "label_str": r[3],
                "text": r[4],
                "created_at": r[5]
            })

        total_raw = len(rows)
        dynamic_user_cap = max(5, min(FEEDBACK_MAX_SAMPLES_PER_USER, int(total_raw * FEEDBACK_MAX_USER_SHARE)))

        curated_samples = []
        seen_hashes = set()

        for user_id, samples in user_buckets.items():
            capped = samples[:dynamic_user_cap]
            for s in capped:
                if s["message_hash"] not in seen_hashes:
                    seen_hashes.add(s["message_hash"])
                    curated_samples.append(s)

        if max_total_samples and len(curated_samples) > max_total_samples:
            curated_samples = curated_samples[:max_total_samples]

        return curated_samples
