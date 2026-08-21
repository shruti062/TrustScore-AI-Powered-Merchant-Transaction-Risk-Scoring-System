import random
from datetime import datetime

from flask import Flask, jsonify, request, render_template

import database
import model as risk_model

app = Flask(
    __name__,
    template_folder="../frontend",
    static_folder="../frontend",
)
try:
    ML_MODEL = risk_model.load_model()
except FileNotFoundError:
    ML_MODEL = None
    print("WARNING: risk_model.pkl not found. Run 'python model.py' first.")

database.init_db()

# Page routes

@app.route("/")
def dashboard():
    return render_template("index.html")

# API routes

@app.route("/api/score-transaction", methods=["POST"])
def score_transaction():
    """
    Score a single transaction.

    Expected JSON body:
    {
        "txn_id": "T12345",
        "merchant_id": "M100",
        "amount": 4500,
        "hour_of_day": 14,
        "location_mismatch": 0,
        "new_device_flag": 1,
        "velocity_last_hour": 2
    }
    """
    if ML_MODEL is None:
        return jsonify({"error": "Model not trained yet"}), 500

    data = request.get_json()

    required_fields = [
        "amount", "hour_of_day", "location_mismatch",
        "new_device_flag", "velocity_last_hour",
    ]
    missing = [f for f in required_fields if f not in data]
    if missing:
        return jsonify({"error": f"Missing fields: {missing}"}), 400

    # is_odd_hour is derived, not sent by the client
    features = {
        "amount": data["amount"],
        "hour_of_day": data["hour_of_day"],
        "is_odd_hour": 1 if data["hour_of_day"] < 6 or data["hour_of_day"] > 23 else 0,
        "location_mismatch": data["location_mismatch"],
        "new_device_flag": data["new_device_flag"],
        "velocity_last_hour": data["velocity_last_hour"],
    }

    result = risk_model.score_transaction(ML_MODEL, features)

    txn_id = data.get("txn_id", f"T{random.randint(100000, 999999)}")
    merchant_id = data.get("merchant_id", "UNKNOWN")

    database.save_scored_transaction(txn_id, merchant_id, features, result)

    return jsonify({
        "txn_id": txn_id,
        "merchant_id": merchant_id,
        **result,
    })


@app.route("/api/simulate-transaction", methods=["POST"])
def simulate_transaction():
    
    if ML_MODEL is None:
        return jsonify({"error": "Model not trained yet"}), 500

    merchant_id = f"M{random.randint(100, 139)}"
    hour = random.randint(0, 23)

    features = {
        "amount": round(random.expovariate(1 / 3000), 2),
        "hour_of_day": hour,
        "is_odd_hour": 1 if hour < 6 or hour > 23 else 0,
        "location_mismatch": random.choices([0, 1], weights=[75, 25])[0],
        "new_device_flag": random.choices([0, 1], weights=[80, 20])[0],
        "velocity_last_hour": random.choices([1, 2, 3, 5, 8], weights=[60, 20, 10, 7, 3])[0],
    }

    result = risk_model.score_transaction(ML_MODEL, features)
    txn_id = f"T{random.randint(100000, 999999)}"

    database.save_scored_transaction(txn_id, merchant_id, features, result)

    return jsonify({
        "txn_id": txn_id,
        "merchant_id": merchant_id,
        **features,
        **result,
    })


@app.route("/api/recent-transactions")
def recent_transactions():
    limit = request.args.get("limit", default=50, type=int)
    return jsonify(database.get_recent_transactions(limit))


@app.route("/api/merchant-summary")
def merchant_summary():
    return jsonify(database.get_merchant_summary())


if __name__ == "__main__":
    app.run(debug=True, port=5000)
