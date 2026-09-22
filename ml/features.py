import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import MinMaxScaler
from sklearn.feature_selection import chi2, mutual_info_classif, f_classif

from ml.preprocess import clean_text_for_nlp, extract_features_df


class SecurityFeatureTransformer(BaseEstimator, TransformerMixin):
    """Custom Scikit-Learn transformer that extracts dense security and linguistic features."""
    def __init__(self):
        self.scaler = MinMaxScaler()
        self.feature_names_ = []

    def fit(self, X, y=None):
        df_feat = extract_features_df(X)
        self.feature_names_ = df_feat.columns.tolist()
        self.scaler.fit(df_feat)
        return self

    def transform(self, X):
        df_feat = extract_features_df(X)
        scaled_feat = self.scaler.transform(df_feat)
        return sparse.csr_matrix(scaled_feat)

    def fit_transform(self, X, y=None):
        df_feat = extract_features_df(X)
        self.feature_names_ = df_feat.columns.tolist()
        scaled_feat = self.scaler.fit_transform(df_feat)
        return sparse.csr_matrix(scaled_feat)

    def get_feature_names_out(self, input_features=None):
        return np.array(self.feature_names_)


class TextCleanerTransformer(BaseEstimator, TransformerMixin):
    """Custom transformer to clean and sanitize input text strings."""
    def fit(self, X, y=None):
        return self

    def transform(self, X):
        return [clean_text_for_nlp(t) for t in X]


def build_feature_pipeline():
    """Builds a combined FeatureUnion combining sublinear Word TF-IDF + Char N-Grams + Security Features."""
    word_tfidf = TfidfVectorizer(
        ngram_range=(1, 2),
        min_df=3,
        max_features=10000,
        sublinear_tf=True,
        token_pattern=r'(?u)\b\w+\b'
    )
    
    char_tfidf = TfidfVectorizer(
        analyzer='char_wb',
        ngram_range=(3, 4),
        min_df=15,
        max_features=4000,
        sublinear_tf=True
    )
    
    security_extractor = SecurityFeatureTransformer()
    return word_tfidf, char_tfidf, security_extractor


import warnings
warnings.filterwarnings('ignore')

def compute_statistical_tests(X_text: list, y: np.ndarray, top_n: int = 25) -> dict:
    """Performs Chi-Square hypothesis testing and Mutual Information ranking on NLP features."""
    cleaned_texts = [clean_text_for_nlp(t) for t in X_text]
    
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=3, max_features=1500, binary=True)
    X_tfidf = vectorizer.fit_transform(cleaned_texts)
    feature_names = np.array(vectorizer.get_feature_names_out())
    
    chi2_scores, p_values = chi2(X_tfidf, y)
    top_chi2_idx = np.argsort(chi2_scores)[::-1][:top_n]
    
    chi2_results = []
    for idx in top_chi2_idx:
        chi2_results.append({
            "token": str(feature_names[idx]),
            "chi2_score": round(float(chi2_scores[idx]), 2),
            "p_value": float(f"{p_values[idx]:.2e}"),
            "statistically_significant": bool(p_values[idx] < 0.01)
        })

    mi_scores = mutual_info_classif(X_tfidf, y, discrete_features=True, random_state=42)
    top_mi_idx = np.argsort(mi_scores)[::-1][:top_n]
    
    mi_results = []
    for idx in top_mi_idx:
        mi_results.append({
            "token": str(feature_names[idx]),
            "mutual_info": round(float(mi_scores[idx]), 4)
        })

    df_sec = extract_features_df(X_text)
    f_scores, f_pvals = f_classif(df_sec, y)
    
    sec_results = []
    for col, f_val, p_val in sorted(zip(df_sec.columns, f_scores, f_pvals), key=lambda x: x[1], reverse=True):
        sec_results.append({
            "feature": col,
            "f_statistic": round(float(f_val), 2),
            "p_value": float(f"{p_val:.2e}")
        })
        
    return {
        "chi2_top_features": chi2_results,
        "mutual_info_top_features": mi_results,
        "security_features_anova": sec_results
    }
