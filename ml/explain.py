import os
import re
import gc
import joblib
import numpy as np
from scipy import sparse
from ml.preprocess import clean_text_for_nlp, extract_linguistic_and_security_features, TARGET_BRANDS, FREE_EMAIL_DOMAINS


class ModelExplainer:
    def __init__(self, models_path='models/trained_models.joblib',
                 word_vec_path='models/word_vectorizer.joblib',
                 char_vec_path='models/char_vectorizer.joblib',
                 sec_ext_path='models/security_extractor.joblib'):
        self.models_path = models_path
        self.individual_dir = 'models/individual'
        self._loaded_models = {}

        self.word_vec = joblib.load(word_vec_path)
        self.char_vec = char_vec_path and joblib.load(char_vec_path)
        self.sec_extractor = joblib.load(sec_ext_path)

        self.word_feature_names = self.word_vec.get_feature_names_out()
        self.word_vocab = {term: idx for idx, term in enumerate(self.word_feature_names)}

        self.lr_model = self.get_model('Logistic Regression')
        self.nb_model = self.get_model('Naive Bayes')

        if self.lr_model is not None and hasattr(self.lr_model, 'coef_'):
            self.word_weights = self.lr_model.coef_[0][:len(self.word_feature_names)]
        else:
            self.word_weights = np.zeros(len(self.word_feature_names))

        if self.nb_model is not None and hasattr(self.nb_model, 'feature_log_prob_'):
            self.nb_log_ratios = self.nb_model.feature_log_prob_[1][:len(self.word_feature_names)] - \
                                 self.nb_model.feature_log_prob_[0][:len(self.word_feature_names)]
        else:
            self.nb_log_ratios = np.zeros(len(self.word_feature_names))
        
        gc.collect()

    def get_model(self, model_name: str):
        if model_name in self._loaded_models:
            return self._loaded_models[model_name]

        safe_name = model_name.lower().replace(' ', '_').replace('(', '').replace(')', '')
        indiv_path = os.path.join(self.individual_dir, f"{safe_name}.joblib")
        if os.path.exists(indiv_path):
            try:
                m = joblib.load(indiv_path)
                self._loaded_models[model_name] = m
                return m
            except Exception as e:
                print(f"[ModelExplainer] Error loading {indiv_path}: {e}")

        if not hasattr(self, '_all_monolithic_models') and os.path.exists(self.models_path):
            try:
                self._all_monolithic_models = joblib.load(self.models_path)
            except Exception:
                self._all_monolithic_models = {}

        if hasattr(self, '_all_monolithic_models') and model_name in self._all_monolithic_models:
            return self._all_monolithic_models[model_name]

        return None

    def transform_text(self, text: str):
        cleaned = clean_text_for_nlp(text)
        X_w = self.word_vec.transform([cleaned])
        X_c = self.char_vec.transform([cleaned])
        X_s = self.sec_extractor.transform([text])
        return sparse.hstack([X_w, X_c, X_s]).tocsr()

    def explain(self, text: str, model_name: str = "Stacking Ensemble") -> dict:
        model = self.get_model(model_name)
        if model is None:
            model = self.get_model("Stacking Ensemble") or self.get_model("Logistic Regression")
            
        X_feat = self.transform_text(text)

        if hasattr(model, "predict_proba"):
            probs = model.predict_proba(X_feat)[0]
            risk_score = float(probs[1])
        elif hasattr(model, "decision_function"):
            df_val = float(model.decision_function(X_feat)[0])
            risk_score = float(1.0 / (1.0 + np.exp(-np.clip(df_val, -20.0, 20.0))))
        else:
            pred_val = float(model.predict(X_feat)[0])
            risk_score = 1.0 if pred_val > 0.5 else 0.0

        risk_score = float(np.clip(risk_score, 0.0, 1.0))

        is_spam = bool(risk_score >= 0.50)
        label = "Spam / Phishing Scam" if is_spam else "Legitimate Email"

        if risk_score >= 0.80:
            threat_level = "CRITICAL THREAT"
            threat_color = "red"
        elif risk_score >= 0.50:
            threat_level = "SUSPICIOUS PHISHING"
            threat_color = "amber"
        elif risk_score >= 0.20:
            threat_level = "LOW RISK"
            threat_color = "blue"
        else:
            threat_level = "VERIFIED SAFE"
            threat_color = "green"

        sec_signals = extract_linguistic_and_security_features(text)
        triggers = []
        lower = text.lower()
        
        if sec_signals['has_micro_fee_trap'] > 0 or re.search(r'(?:access\s+fee|digital\s+id|no\s+internship\s+fee|id\s+card\s+issuance|platform\s+access)', lower):
            triggers.append({
                "category": "Micro-Fee / ID Card Scam Trap",
                "severity": "CRITICAL",
                "detail": "Requests access fee, Digital ID card issuance fee, or platform maintenance charge under deceptive 'no internship fee' framing."
            })

        if sec_signals['financial_score'] > 0:
            triggers.append({
                "category": "Financial Advance Fee / Charge",
                "severity": "CRITICAL",
                "detail": "Mentions registration fee, access charge, deposit, payment, UPI, or cash transaction."
            })

        if sec_signals['accreditation_score'] > 0 and (sec_signals['financial_score'] > 0 or sec_signals['has_micro_fee_trap'] > 0):
            triggers.append({
                "category": "Regulatory Impersonation (MCA/MSME/AICTE)",
                "severity": "HIGH",
                "detail": "Leverages MCA, MSME, AICTE, or ISO certification claims alongside upfront charges or non-standard onboarding."
            })

        if re.search(r'(?:maang|bootcamp|extra\s+\d+%\s+off|coupon\s+code|final\s+call|offer\s+ends\s+@|talk\s+to\s+a\s+counsellor)', lower):
            triggers.append({
                "category": "Commercial Bootcamp / Course Marketing Spam",
                "severity": "HIGH",
                "detail": "High-pressure course or bootcamp sales pitch disguised with countdown urgency, discounts, or placement guarantees."
            })

        if re.search(r'(?:\[update\]\s+your\s+application\s+has\s+been\s+accepted|represent\s+.*?at\s+(?:your\s+)?(?:campus|college|vtu))', lower):
            triggers.append({
                "category": "Deceptive Application Acceptance / Campus Bait",
                "severity": "HIGH",
                "detail": "Falsely claims application was accepted or recruits for unpaid student campus ambassador promotion."
            })

        if sec_signals['has_free_email']:
            triggers.append({
                "category": "Domain Spoofing",
                "severity": "HIGH",
                "detail": "Sender is using a free public email provider (Gmail/Proton/Yahoo) rather than an official corporate domain."
            })
            
        if sec_signals['has_short_url'] or sec_signals['has_suspicious_tld']:
            triggers.append({
                "category": "Suspicious Links",
                "severity": "CRITICAL",
                "detail": "Contains URL shortener, tracking redirect, or unverified domain with suspicious TLD."
            })

        if sec_signals['urgency_score'] > 0:
            triggers.append({
                "category": "Psychological Urgency & Scarcity",
                "severity": "MEDIUM",
                "detail": "Uses urgency pressure ('immediately', 'expires tonight', 'final hours', 'only a few slots left')."
            })

        if sec_signals['brand_mentions'] > 0 and not sec_signals['has_company_email'] and (sec_signals['has_free_email'] or sec_signals['financial_score'] > 0):
            triggers.append({
                "category": "Brand Impersonation",
                "severity": "CRITICAL",
                "detail": "Mentions major corporate brands alongside unverified email, payment demands, or commercial upselling."
            })

        if sec_signals['has_ats_portal']:
            triggers.append({
                "category": "Verified ATS Portal",
                "severity": "SAFE",
                "detail": "Uses verified corporate applicant tracking portal (Greenhouse, Lever, Keka, etc.)."
            })

        if sec_signals['has_company_email']:
            triggers.append({
                "category": "Corporate Domain",
                "severity": "SAFE",
                "detail": "Sent from authentic corporate work email domain."
            })

        tokens = re.findall(r'\b\w+\b|[^\w\s]', text)
        token_attributions = []
        
        for tok in tokens:
            tok_lower = tok.lower()
            weight = 0.0
            if tok_lower in self.word_vocab:
                idx = self.word_vocab[tok_lower]
                weight = float(self.word_weights[idx]) if idx < len(self.word_weights) else 0.0

            if re.match(r'^(deposit|fee|fees|charge|charges|access|id|digital|issuance|upi|gpay|paytm|rupees|rupee|inr|₹|guaranteed|telegram|whatsapp|bootcamp|maang|coupon|counsellor|scholarship|89|99|199|499)$', tok_lower):
                weight = max(weight, 1.8)
            elif re.match(r'^(interview|portal|responsibilities|stipend|hybrid|bangalore|pune|hyderabad)$', tok_lower):
                weight = min(weight, -0.8)

            tok_type = "risk" if weight > 0.3 else ("safe" if weight < -0.3 else "neutral")
            token_attributions.append({
                "token": tok,
                "weight": round(weight, 3),
                "type": tok_type
            })

        prior_prob = 0.6044
        prior_log_odds = float(np.log(prior_prob / (1 - prior_prob)))
        evidence_score = float(np.log(risk_score / (1 - risk_score + 1e-8))) - prior_log_odds

        bayes_stats = {
            "prior_spam_probability": round(prior_prob, 4),
            "prior_log_odds": round(prior_log_odds, 4),
            "evidence_log_likelihood_ratio": round(evidence_score, 4),
            "calibrated_posterior_risk": round(risk_score, 4),
            "model_used": model_name
        }

        model_consensus = {}
        primary_names = ['Logistic Regression', 'Naive Bayes', 'Support Vector Machine', 'Stacking Ensemble']
        for m_name in primary_names:
            m_obj = self.get_model(m_name)
            if m_obj is None:
                continue
            if hasattr(m_obj, "predict_proba"):
                m_risk = float(m_obj.predict_proba(X_feat)[0, 1])
            elif hasattr(m_obj, "decision_function"):
                df_val = float(m_obj.decision_function(X_feat)[0])
                m_risk = float(1.0 / (1.0 + np.exp(-np.clip(df_val, -20.0, 20.0))))
            else:
                pred_v = float(m_obj.predict(X_feat)[0])
                m_risk = 1.0 if pred_v > 0.5 else 0.0
            m_risk = float(np.clip(m_risk, 0.0, 1.0))
            model_consensus[m_name] = {
                "risk_score": round(m_risk, 4),
                "classification": "Spam" if m_risk >= 0.5 else "Legitimate"
            }

        return {
            "label": label,
            "is_spam": is_spam,
            "risk_score": round(risk_score, 4),
            "threat_level": threat_level,
            "threat_color": threat_color,
            "model_used": model_name,
            "security_triggers": triggers,
            "token_attributions": token_attributions,
            "bayes_statistics": bayes_stats,
            "model_consensus": model_consensus,
            "linguistic_metrics": {
                "char_length": sec_signals['char_len'],
                "word_count": sec_signals['word_count'],
                "uppercase_ratio": round(sec_signals['uppercase_ratio'], 3),
                "type_token_ratio": round(sec_signals['type_token_ratio'], 3),
                "financial_trigger_count": sec_signals['financial_score'],
                "urgency_trigger_count": sec_signals['urgency_score']
            }
        }
