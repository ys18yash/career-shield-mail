import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml.explain import ModelExplainer
from ml.preprocess import clean_text_for_nlp

def test_explainer_inference():
    explainer = ModelExplainer()
    
    text = "SkillInfyTech 4-Weeks Internship. Access Fee: ₹89 only via UPI."
    res = explainer.explain(text, model_name="Stacking Ensemble")
    assert res is not None
    assert "risk_score" in res
    assert 0.0 <= res["risk_score"] <= 1.0
    assert res["is_spam"] == True
    assert len(res["security_triggers"]) > 0
    assert len(res["model_consensus"]) >= 7
    print("  [PASS] ML Explainer Inference & Dimension Test")

def test_unicode_and_empty_edge_cases():
    explainer = ModelExplainer()
    
    res_empty = explainer.explain("", model_name="Stacking Ensemble")
    assert res_empty is not None
    assert 0.0 <= res_empty["risk_score"] <= 1.0
    
    res_unicode = explainer.explain("🚀💰🔥 ₹9999 $$$ --- 🎉 !!!", model_name="Stacking Ensemble")
    assert res_unicode is not None
    assert 0.0 <= res_unicode["risk_score"] <= 1.0
    print("  [PASS] Unicode & Empty Edge Case Test")

def test_all_models_callable():
    explainer = ModelExplainer()
    sample = "Dear Candidate, We are pleased to extend an offer for the Software Engineering Intern role in Bangalore with Google India. Monthly stipend INR 1,15,000. Review on careers.google.com."
    
    models = [
        "Naive Bayes", "Logistic Regression", "Support Vector Machine",
        "Random Forest", "Extra Trees Ensemble", "XGBoost",
        "Deep Neural Net (MLP)", "Stacking Ensemble"
    ]
    for m in models:
        r = explainer.explain(sample, model_name=m)
        assert 0.0 <= r["risk_score"] <= 1.0
        assert "threat_level" in r
        assert "security_triggers" in r
        assert "token_attributions" in r
    print("  [PASS] All 8 Model Paradigms Callable & Schema Compliant Test")

if __name__ == "__main__":
    print("RUNNING ML INFERENCE TESTS")
    test_explainer_inference()
    test_unicode_and_empty_edge_cases()
    test_all_models_callable()
    print("ALL ML INFERENCE TESTS PASSED.")
