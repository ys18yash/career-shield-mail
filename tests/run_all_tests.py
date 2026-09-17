import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_data_integrity import test_dataset_partitions, test_leakage_checks
from tests.test_ml_inference import test_explainer_inference, test_unicode_and_empty_edge_cases, test_all_models_callable
from tests.test_api import test_api_routes
from tests.test_security_hardening import test_xss_and_html_injection, test_oversized_payload_truncation, test_safe_url_extraction
from tests.test_gmail_integration import test_mock_gmail_sync
from tests.test_end_to_end import test_full_system_flow
from tests.test_feedback_continuous_learning import (
    test_personal_feedback_submission_and_updates,
    test_multi_user_isolation_and_conflict_detection,
    test_per_user_contribution_caps,
    test_candidate_dataset_snapshotting_preserves_master,
    test_validation_gate_and_rollback,
    test_feedback_analytics_and_status_endpoints
)

def run_feedback_tests():
    test_personal_feedback_submission_and_updates()
    test_multi_user_isolation_and_conflict_detection()
    test_per_user_contribution_caps()
    test_candidate_dataset_snapshotting_preserves_master()
    test_validation_gate_and_rollback()
    test_feedback_analytics_and_status_endpoints()

def run_master_test_suite():
    print("=" * 80)
    print("CAREERSHIELD MAIL: MASTER REPRODUCIBILITY & SYSTEM VERIFICATION SUITE")
    print("=" * 80)

    t0 = time.time()
    test_suites = [
        ("1. Dataset Partitions & Records", test_dataset_partitions),
        ("2. Zero Data / Text Leakage", test_leakage_checks),
        ("3. ML Inference & 14,022-Dim Pipeline", test_explainer_inference),
        ("4. Unicode, HTML & Edge Cases", test_unicode_and_empty_edge_cases),
        ("5. 8 Model Paradigms Callable", test_all_models_callable),
        ("6. Security Sanitization & XSS Defense", test_xss_and_html_injection),
        ("7. Payload Size Hardening", test_oversized_payload_truncation),
        ("8. Safe URL Extraction", test_safe_url_extraction),
        ("9. FastAPI Core Endpoints", test_api_routes),
        ("10. Gmail IMAP & Mock Sync", test_mock_gmail_sync),
        ("11. End-to-End Threat Hunting Flow", test_full_system_flow),
        ("12. Multi-Tenant HITL Feedback & Continuous Learning", run_feedback_tests),
    ]

    passed = 0
    failed = 0

    for name, fn in test_suites:
        print(f"\n[EXEC] Running Test: {name}...")
        try:
            fn()
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {name}: {str(e)}")
            failed += 1

    print("\n" + "=" * 80)
    print(f"TEST SUITE COMPLETE: {passed}/{len(test_suites)} SUITES PASSED in {time.time() - t0:.2f}s")
    if failed == 0:
        print(">> VERIFICATION GATE STATUS: [PASS] 100% SUCCESS")
    else:
        print(f">> VERIFICATION GATE STATUS: [FAIL] {failed} test(s) failed")
    print("=" * 80)

if __name__ == "__main__":
    run_master_test_suite()
