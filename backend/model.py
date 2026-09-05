
import json
import pandas as pd
import joblib
import shap
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, roc_auc_score, confusion_matrix,
)
from xgboost import XGBClassifier

FEATURE_COLUMNS = [
    "amount",
    "hour_of_day",
    "is_odd_hour",
    "location_mismatch",
    "new_device_flag",
    "velocity_last_hour",
    "amount_deviation_ratio",
]

MODEL_PATH = "risk_model.pkl"
METRICS_PATH = "metrics.json"


def evaluate(name, model, X_test, y_test):
    preds = model.predict(X_test)
    probs = model.predict_proba(X_test)[:, 1]

    cm = confusion_matrix(y_test, preds).tolist()

    return {
        "name": name,
        "accuracy": round(accuracy_score(y_test, preds), 4),
        "precision": round(precision_score(y_test, preds, zero_division=0), 4),
        "recall": round(recall_score(y_test, preds, zero_division=0), 4),
        "f1_score": round(f1_score(y_test, preds, zero_division=0), 4),
        "roc_auc": round(roc_auc_score(y_test, probs), 4),
        "confusion_matrix": {
            "true_negative": cm[0][0], "false_positive": cm[0][1],
            "false_negative": cm[1][0], "true_positive": cm[1][1],
        },
    }


def train_and_save_model(csv_path="transactions.csv"):
    df = pd.read_csv(csv_path)
    X = df[FEATURE_COLUMNS]
    y = df["is_fraud"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    candidates = {
        "Logistic Regression": LogisticRegression(
            max_iter=5000, class_weight="balanced"
        ),
        "Random Forest": RandomForestClassifier(
            n_estimators=150, max_depth=8, random_state=42,
            class_weight="balanced",
        ),
        "XGBoost": XGBClassifier(
            n_estimators=150, max_depth=5, learning_rate=0.1,
            eval_metric="logloss", random_state=42,
            scale_pos_weight=(y_train == 0).sum() / (y_train == 1).sum(),
        ),
    }

    results = []
    trained_models = {}

    for name, clf in candidates.items():
        clf.fit(X_train, y_train)
        trained_models[name] = clf
        results.append(evaluate(name, clf, X_test, y_test))
        print(f"\n{name}")
        print(f"  Accuracy:  {results[-1]['accuracy']}")
        print(f"  Precision: {results[-1]['precision']}")
        print(f"  Recall:    {results[-1]['recall']}")
        print(f"  F1 Score:  {results[-1]['f1_score']}")
        print(f"  ROC-AUC:   {results[-1]['roc_auc']}")

    # Pick the best model by ROC-AUC — a good single number for how
    # well a model separates fraud from non-fraud across all thresholds
    best = max(results, key=lambda r: r["roc_auc"])
    best_model = trained_models[best["name"]]

    print(f"\nBest model: {best['name']} (ROC-AUC: {best['roc_auc']})")

    joblib.dump(best_model, MODEL_PATH)
    joblib.dump(best["name"], "best_model_name.pkl")

    # Save a small background sample for SHAP to use later. SHAP needs
    # a reference set of "typical" rows to compare each new prediction
    # against — we keep this tiny (100 rows) since it's only used at
    # explanation time, not for training.
    background_sample = X_train.sample(min(100, len(X_train)), random_state=42)
    joblib.dump(background_sample, "shap_background.pkl")

    with open(METRICS_PATH, "w") as f:
        json.dump({
            "all_models": results,
            "best_model": best["name"],
            "trained_on_rows": len(df),
            "fraud_rate": round(float(y.mean()), 4),
        }, f, indent=2)

    print(f"Saved {MODEL_PATH} and {METRICS_PATH}")
    return best_model


def load_model():
    return joblib.load(MODEL_PATH)


def load_metrics():
    with open(METRICS_PATH) as f:
        return json.load(f)


def score_transaction(model, features: dict, thresholds: dict = None):
    """
    Given a single transaction's features, return a risk score,
    human-readable reasons (rule-based + SHAP-backed), and a
    recommended action.

    thresholds (optional): {"block_threshold": 70, "review_threshold": 35}
    Lets the caller use admin-configured thresholds instead of the
    hardcoded defaults in decide_action().
    """
    row = pd.DataFrame([features])[FEATURE_COLUMNS]

    fraud_probability = model.predict_proba(row)[0][1]
    risk_score = round(fraud_probability * 100, 1)

    reasons = explain_score(features)
    top_shap_features = explain_with_shap(model, row)
    action = decide_action(risk_score, thresholds)

    return {
        "risk_score": risk_score,
        "reasons": reasons,
        "top_contributing_features": top_shap_features,
        "recommended_action": action,
    }


def explain_score(features: dict):
    """
    Simple, rule-based, human-readable reasons for the score. Easier
    for a reviewer to scan quickly than raw SHAP numbers.
    """
    reasons = []

    if features.get("is_odd_hour"):
        reasons.append("Transaction happened outside this merchant's usual hours")
    if features.get("location_mismatch"):
        reasons.append("Billing and shipping city don't match")
    if features.get("new_device_flag"):
        reasons.append("Made from a device we haven't seen for this customer")
    if features.get("velocity_last_hour", 0) >= 4:
        reasons.append(
            f"{features['velocity_last_hour']} transactions from this "
            "customer in the last hour"
        )
    if features.get("amount_deviation_ratio", 1) >= 3:
        reasons.append("Amount is far higher than this merchant's typical transaction")

    if not reasons:
        reasons.append("No major red flags detected")

    return reasons


_SHAP_EXPLAINER_CACHE = {"model_id": None, "explainer": None}


def _get_shap_explainer(model):
    """
    Builds (and caches) the right kind of SHAP explainer depending on
    which model type won the comparison — tree models (Random Forest,
    XGBoost) use the fast TreeExplainer, while Logistic Regression
    needs a background dataset and a general-purpose Explainer.
    Cached so we don't rebuild it on every single request.
    """
    if _SHAP_EXPLAINER_CACHE["model_id"] == id(model):
        return _SHAP_EXPLAINER_CACHE["explainer"]

    model_type = type(model).__name__

    if model_type in ("RandomForestClassifier", "XGBClassifier"):
        explainer = shap.TreeExplainer(model)
    elif model_type == "LogisticRegression":
        # LinearExplainer is fast and exact for linear models —
        # avoids the slow permutation-based general Explainer.
        background = joblib.load("shap_background.pkl")
        explainer = shap.LinearExplainer(model, background)
    else:
        # Fallback for any other model type. Capped at a small
        # background sample (10 rows) so it stays fast enough for
        # live, per-request scoring.
        background = joblib.load("shap_background.pkl").sample(
            min(10, len(joblib.load("shap_background.pkl"))), random_state=42
        )
        explainer = shap.Explainer(model.predict_proba, background)

    _SHAP_EXPLAINER_CACHE["model_id"] = id(model)
    _SHAP_EXPLAINER_CACHE["explainer"] = explainer
    return explainer


def explain_with_shap(model, row: pd.DataFrame, top_n=3):
    """
    Uses SHAP to explain exactly how much each feature contributed to
    THIS specific prediction, in the model's own terms (not just our
    hand-written rules). Returns the top N features pushing the score
    up, with their contribution values.
    """
    try:
        explainer = _get_shap_explainer(model)
        model_type = type(model).__name__

        if model_type in ("RandomForestClassifier", "XGBClassifier"):
            shap_values = explainer.shap_values(row)
            values = shap_values[1][0] if isinstance(shap_values, list) else shap_values[0]
        elif model_type == "LogisticRegression":
            values = explainer.shap_values(row)[0]
        else:
            shap_values = explainer(row)
            values = shap_values.values[0][:, 1]

        contributions = list(zip(FEATURE_COLUMNS, values))
        contributions.sort(key=lambda x: abs(x[1]), reverse=True)

        return [
            {"feature": name, "impact": round(float(val), 3)}
            for name, val in contributions[:top_n]
        ]
    except Exception as e:
        # Fail gracefully rather than break scoring if SHAP hits an
        # edge case — the rule-based reasons still cover explainability.
        print(f"SHAP explanation failed: {e}")
        return []


def decide_action(risk_score: float, thresholds: dict = None) -> str:
    """
    Turns a score into an action using either admin-configured
    thresholds (passed in from the settings table) or sensible
    defaults if none are provided.
    """
    block_at = (thresholds or {}).get("block_threshold", 70)
    review_at = (thresholds or {}).get("review_threshold", 35)

    if risk_score >= block_at:
        return "block"
    elif risk_score >= review_at:
        return "review"
    else:
        return "allow"


if __name__ == "__main__":
    train_and_save_model()
