"""
AirCrewAI — Crew Misconnect Risk Model Training
Trains and evaluates two models:
  1. Logistic Regression (baseline)
  2. XGBoost (main model)

Evaluation uses ROC-AUC, PR-AUC, Precision, Recall, F1.
NOT accuracy — because class imbalance makes accuracy misleading.

Saves trained XGBoost model and scaler to disk for inference.
"""

import os
import json
import pickle
import numpy as np
import pandas as pd

from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    roc_auc_score, average_precision_score,
    precision_score, recall_score, f1_score,
    classification_report, confusion_matrix
)
from xgboost import XGBClassifier
import shap

from features import generate_training_data, get_feature_columns

# ── PATHS ──────────────────────────────────────────────────────────────────────
MODEL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "data", "synthetic"
)
os.makedirs(MODEL_DIR, exist_ok=True)

MODEL_PATH = os.path.join(MODEL_DIR, "xgb_model.pkl")
SCALER_PATH = os.path.join(MODEL_DIR, "scaler.pkl")
FEATURE_COLS_PATH = os.path.join(MODEL_DIR, "feature_cols.json")
EVAL_PATH = os.path.join(MODEL_DIR, "model_evaluation.json")


def evaluate_model(name: str, y_true, y_pred, y_prob) -> dict:
    """Compute and print all evaluation metrics."""
    metrics = {
        "model": name,
        "roc_auc": round(roc_auc_score(y_true, y_prob), 4),
        "pr_auc": round(average_precision_score(y_true, y_prob), 4),
        "precision": round(precision_score(y_true, y_pred, zero_division=0), 4),
        "recall": round(recall_score(y_true, y_pred, zero_division=0), 4),
        "f1": round(f1_score(y_true, y_pred, zero_division=0), 4),
    }

    print(f"\n{'='*50}")
    print(f"  {name}")
    print(f"{'='*50}")
    print(f"  ROC-AUC:   {metrics['roc_auc']:.4f}")
    print(f"  PR-AUC:    {metrics['pr_auc']:.4f}  (key metric for imbalanced data)")
    print(f"  Precision: {metrics['precision']:.4f}")
    print(f"  Recall:    {metrics['recall']:.4f}  (critical — missing a misconnect is costly)")
    print(f"  F1:        {metrics['f1']:.4f}")
    print()
    print("  Why recall matters operationally:")
    print("  A false negative = crew member predicted safe but actually misconnects.")
    print("  This causes a downstream flight to lose coverage at the last minute,")
    print("  which is far more costly than a false positive (being cautious).")
    print()
    print("  Confusion Matrix:")
    cm = confusion_matrix(y_true, y_pred)
    print(f"  TN={cm[0,0]}  FP={cm[0,1]}")
    print(f"  FN={cm[1,0]}  TP={cm[1,1]}")

    return metrics


def train():
    print("=== AirCrewAI — Crew Misconnect Risk Model Training ===")
    print()

    # ── GENERATE TRAINING DATA ─────────────────────────────────────────────────
    print("Generating synthetic training data...")
    df = generate_training_data(5000)
    feature_cols = get_feature_columns()

    X = df[feature_cols]
    y = df["misconnect"]

    print(f"\nDataset: {len(df)} samples")
    print(f"Misconnect rate: {y.mean():.1%} (class imbalance present)")
    print(f"Features: {len(feature_cols)}")

    # ── TRAIN/TEST SPLIT ───────────────────────────────────────────────────────
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )
    print(f"\nTrain: {len(X_train)} | Test: {len(X_test)}")

    # ── SCALING (for Logistic Regression) ─────────────────────────────────────
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    results = []

    # ── BASELINE: LOGISTIC REGRESSION ─────────────────────────────────────────
    print("\nTraining Logistic Regression baseline...")
    lr = LogisticRegression(random_state=42, max_iter=1000, class_weight="balanced")
    lr.fit(X_train_scaled, y_train)

    lr_pred = lr.predict(X_test_scaled)
    lr_prob = lr.predict_proba(X_test_scaled)[:, 1]

    lr_metrics = evaluate_model("Logistic Regression (Baseline)", y_test, lr_pred, lr_prob)
    results.append(lr_metrics)

    # ── MAIN MODEL: XGBOOST ────────────────────────────────────────────────────
    print("\nTraining XGBoost...")

    # Calculate scale_pos_weight to handle class imbalance
    neg_count = (y_train == 0).sum()
    pos_count = (y_train == 1).sum()
    scale_pos_weight = neg_count / pos_count
    print(f"  scale_pos_weight: {scale_pos_weight:.2f} (handles class imbalance)")

    xgb = XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=scale_pos_weight,
        random_state=42,
        eval_metric="aucpr",
        verbosity=0,
    )
    xgb.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False,
    )

    xgb_pred = xgb.predict(X_test)
    xgb_prob = xgb.predict_proba(X_test)[:, 1]

    xgb_metrics = evaluate_model("XGBoost (Main Model)", y_test, xgb_pred, xgb_prob)
    results.append(xgb_metrics)

    # ── CROSS VALIDATION ───────────────────────────────────────────────────────
    print("\nCross-validation (5-fold, ROC-AUC):")
    cv_scores = cross_val_score(xgb, X, y, cv=5, scoring="f1")
    print(f"  Mean: {cv_scores.mean():.4f} (+/- {cv_scores.std() * 2:.4f})")

    xgb_metrics["cv_roc_auc_mean"] = round(cv_scores.mean(), 4)
    xgb_metrics["cv_roc_auc_std"] = round(cv_scores.std(), 4)

    # ── FEATURE IMPORTANCE ─────────────────────────────────────────────────────
    print("\nXGBoost Feature Importance (by gain):")
    importance = xgb.get_booster().get_score(importance_type="gain")
    importance_sorted = sorted(importance.items(), key=lambda x: x[1], reverse=True)
    for feat, score in importance_sorted[:10]:
        print(f"  {feat:<35} {score:.1f}")

    # ── SHAP EXPLANATIONS ──────────────────────────────────────────────────────
    print("\nComputing SHAP values (sample of 200 test instances)...")
    shap_sample = X_test.sample(min(200, len(X_test)), random_state=42)
    explainer = shap.TreeExplainer(xgb.get_booster())
    shap_values = explainer.shap_values(shap_sample)
   

    # Global feature importance from SHAP
    shap_importance = pd.DataFrame({
        "feature": feature_cols,
        "mean_abs_shap": np.abs(shap_values).mean(axis=0)
    }).sort_values("mean_abs_shap", ascending=False)

    print("\nSHAP Global Feature Importance:")
    for _, row in shap_importance.iterrows():
        bar = "█" * int(row["mean_abs_shap"] * 50)
        print(f"  {row['feature']:<35} {bar} {row['mean_abs_shap']:.4f}")

    # ── SAVE ARTIFACTS ─────────────────────────────────────────────────────────
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(xgb, f)
    print(f"\nXGBoost model saved to {MODEL_PATH}")

    with open(SCALER_PATH, "wb") as f:
        pickle.dump(scaler, f)
    print(f"Scaler saved to {SCALER_PATH}")

    with open(FEATURE_COLS_PATH, "w") as f:
        json.dump(feature_cols, f)
    print(f"Feature columns saved to {FEATURE_COLS_PATH}")

    eval_results = {
        "training_samples": len(X_train),
        "test_samples": len(X_test),
        "misconnect_rate": round(float(y.mean()), 4),
        "models": results,
        "shap_global_importance": shap_importance.to_dict(orient="records"),
        "winner": "XGBoost" if xgb_metrics["roc_auc"] > lr_metrics["roc_auc"] else "LogisticRegression",
    }

    with open(EVAL_PATH, "w") as f:
        json.dump(eval_results, f, indent=2)
    print(f"Evaluation results saved to {EVAL_PATH}")

    print("\n=== Training Complete ===")
    print(f"XGBoost ROC-AUC: {xgb_metrics['roc_auc']:.4f}")
    print(f"XGBoost Recall:  {xgb_metrics['recall']:.4f}")
    print(f"LR ROC-AUC:      {lr_metrics['roc_auc']:.4f}")
    print(f"Winner: {eval_results['winner']}")

    return xgb, scaler, feature_cols, eval_results


if __name__ == "__main__":
    train()
