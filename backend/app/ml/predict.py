"""
AirCrewAI — Crew Misconnect Risk Prediction (Inference)
Loads trained XGBoost model and returns misconnect probability + SHAP explanations.
Used by FastAPI endpoints at runtime.
"""

import os
import json
import pickle
import numpy as np
import pandas as pd
from typing import Optional

try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False

# ── PATHS ──────────────────────────────────────────────────────────────────────
DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "data", "synthetic"
)

MODEL_PATH = os.path.join(DATA_DIR, "xgb_model.pkl")
SCALER_PATH = os.path.join(DATA_DIR, "scaler.pkl")
FEATURE_COLS_PATH = os.path.join(DATA_DIR, "feature_cols.json")

# ── LOAD MODEL (singleton) ─────────────────────────────────────────────────────
_model = None
_scaler = None
_feature_cols = None
_explainer = None


def load_model():
    global _model, _scaler, _feature_cols, _explainer

    if _model is not None:
        return _model, _scaler, _feature_cols, _explainer

    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(
            f"Model not found at {MODEL_PATH}. "
            "Run backend/app/ml/train.py first."
        )

    with open(MODEL_PATH, "rb") as f:
        _model = pickle.load(f)

    with open(SCALER_PATH, "rb") as f:
        _scaler = pickle.load(f)

    with open(FEATURE_COLS_PATH) as f:
        _feature_cols = json.load(f)

    _explainer = shap.TreeExplainer(_model) if SHAP_AVAILABLE else None
    print("Model loaded successfully.")

    return _model, _scaler, _feature_cols, _explainer


def predict_misconnect(features: dict) -> dict:
    """
    Predict crew misconnect probability for a single crew connection.

    Args:
        features: dict with feature values (from features.build_crew_features)

    Returns:
        dict with:
          - misconnect_probability: float 0-1
          - risk_level: LOW / MODERATE / HIGH / CRITICAL
          - shap_contributions: list of {feature, value, direction}
          - model_version: str
    """
    model, scaler, feature_cols, explainer = load_model()

    # Build feature vector
    X = pd.DataFrame([features])[feature_cols]

    # Predict probability
    prob = float(model.predict_proba(X)[0, 1])

    # Risk level thresholds
    if prob >= 0.80:
        risk_level = "CRITICAL"
    elif prob >= 0.60:
        risk_level = "HIGH"
    elif prob >= 0.35:
        risk_level = "MODERATE"
    else:
        risk_level = "LOW"

    # SHAP explanation
    top_contributions = []
    if SHAP_AVAILABLE and _explainer is not None:
        shap_values = _explainer.shap_values(X)
        shap_row = shap_values[0]
        contributions = []
    for feat, shap_val in zip(feature_cols, shap_row):
        contributions.append({
            "feature": feat,
            "shap_value": round(float(shap_val), 4),
            "feature_value": round(float(features.get(feat, 0)), 2),
            "direction": "increases_risk" if shap_val > 0 else "decreases_risk",
        })
    contributions.sort(key=lambda x: abs(x["shap_value"]), reverse=True)
    top_contributions = contributions[:5]

    return {
        "misconnect_probability": round(prob, 4),
        "risk_level": risk_level,
        "shap_contributions": top_contributions,
        "model_version": "xgboost_v1",
        "features_used": feature_cols,
    }


def predict_crew_risk_batch(crew_list: list, flights_map: dict,
                             assignments_map: dict, inbound_delay: int = 0) -> list:
    """
    Predict misconnect risk for multiple crew members at once.
    Used by the Operations Overview page to rank all crews by risk.
    """
    from features import build_crew_features, load_synthetic_data

    _, _, _, _, flights_map_loaded, crew_map, airports_map = load_synthetic_data()
    flights_map = flights_map or flights_map_loaded

    results = []

    for crew in crew_list:
        crew_id = crew["crew_id"]

        # Find next assignment for this crew
        next_flight_id = assignments_map.get(crew_id)
        if not next_flight_id:
            continue

        connection_minutes = 45  # default
        delay = inbound_delay

        try:
            feat = build_crew_features(
                crew_id=crew_id,
                inbound_delay=delay,
                connection_minutes=connection_minutes,
                outbound_flight_id=next_flight_id,
                flights_map=flights_map,
                crew_map=crew_map,
                airports_map=airports_map,
            )
            result = predict_misconnect(feat)
            result["crew_id"] = crew_id
            result["next_flight_id"] = next_flight_id
            results.append(result)
        except Exception as e:
            print(f"Error predicting for {crew_id}: {e}")
            continue

    # Sort by risk
    results.sort(key=lambda x: x["misconnect_probability"], reverse=True)
    return results


if __name__ == "__main__":
    # Test prediction
    print("=== AirCrewAI — Misconnect Risk Prediction Test ===")
    print()

    # Simulate the demo scenario: crew C021 with inbound delay of 105 min
    test_features = {
        "inbound_delay_minutes": 105,
        "scheduled_connection_minutes": 45,
        "effective_connection_minutes": max(0, 45 - 105),
        "airport_congestion_index": 0.80,
        "is_hub_airport": 1,
        "hour_of_day": 9,
        "is_peak_hour": 1,
        "accumulated_duty_minutes": 240,
        "remaining_duty_minutes": 360,
        "legs_flown_today": 2,
        "aircraft_qualified": 1,
        "turnaround_time": 45,
        "weather_severity": 2,
        "network_congestion": 0.85,
    }

    print("Input scenario:")
    print(f"  Inbound delay: {test_features['inbound_delay_minutes']} min")
    print(f"  Scheduled connection: {test_features['scheduled_connection_minutes']} min")
    print(f"  Effective connection: {test_features['effective_connection_minutes']} min")
    print(f"  Airport congestion: {test_features['airport_congestion_index']}")
    print()

    result = predict_misconnect(test_features)

    print(f"Misconnect Probability: {result['misconnect_probability']:.1%}")
    print(f"Risk Level: {result['risk_level']}")
    print()
    print("Top SHAP Contributors:")
    for c in result["shap_contributions"]:
        direction = "+" if c["direction"] == "increases_risk" else "-"
        print(f"  {direction} {c['feature']:<35} SHAP: {c['shap_value']:+.4f}")
