import pandas as pd
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report

FEATURE_COLUMNS = [
    "amount",
    "hour_of_day",
    "is_odd_hour",
    "location_mismatch",
    "new_device_flag",
    "velocity_last_hour",
]

MODEL_PATH = "risk_model.pkl"


def train_and_save_model(csv_path="transactions.csv"):
    """Train the model on our transaction dataset and save it to disk."""
    df = pd.read_csv(csv_path)

    X = df[FEATURE_COLUMNS]
    y = df["is_fraud"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model = RandomForestClassifier(
        n_estimators=150,
        max_depth=8,
        random_state=42,
        class_weight="balanced",  # fraud is rare, so weight it fairly
    )
    model.fit(X_train, y_train)

    predictions = model.predict(X_test)
    print("Model accuracy:", accuracy_score(y_test, predictions))
    print(classification_report(y_test, predictions))

    joblib.dump(model, MODEL_PATH)
    print(f"Model saved to {MODEL_PATH}")

    return model


def load_model():
    """Load the previously trained model from disk."""
    return joblib.load(MODEL_PATH)


def score_transaction(model, features: dict):
    row = pd.DataFrame([features])[FEATURE_COLUMNS]

    fraud_probability = model.predict_proba(row)[0][1]
    risk_score = round(fraud_probability * 100, 1)

    reasons = explain_score(features)
    action = decide_action(risk_score)

    return {
        "risk_score": risk_score,
        "reasons": reasons,
        "recommended_action": action,
    }


def explain_score(features: dict):
    reasons = []

    if features.get("is_odd_hour"):
        reasons.append("Transaction happened late at night / early morning")
    if features.get("location_mismatch"):
        reasons.append("Billing and shipping city don't match")
    if features.get("new_device_flag"):
        reasons.append("Made from a device we haven't seen for this customer")
    if features.get("velocity_last_hour", 0) >= 4:
        reasons.append(
            f"{features['velocity_last_hour']} transactions from this "
            "customer in the last hour"
        )
    if features.get("amount", 0) > 50000:
        reasons.append("Unusually high transaction amount")

    if not reasons:
        reasons.append("No major red flags detected")

    return reasons


def decide_action(risk_score: float) -> str:
    if risk_score >= 70:
        return "block"
    elif risk_score >= 35:
        return "review"
    else:
        return "allow"


if __name__ == "__main__":
    train_and_save_model()
