import io
import csv
import random
from functools import wraps

from flask import Flask, jsonify, request, render_template, Response
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required,
    get_jwt_identity, get_jwt,
)

import database
import auth
import model as risk_model
import retrain_with_feedback as retrainer
from config import Config

app = Flask(
    __name__,
    template_folder="../frontend/templates",
    static_folder="../frontend/static",
    static_url_path="/static",
)

app.config["JWT_SECRET_KEY"] = Config.JWT_SECRET_KEY
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = Config.JWT_ACCESS_TOKEN_EXPIRES
jwt = JWTManager(app)

try:
    ML_MODEL = risk_model.load_model()
except FileNotFoundError:
    ML_MODEL = None
    print("WARNING: risk_model.pkl not found. Run 'python model.py' first.")

database.init_db()


def admin_required(fn):
    """Route decorator: only allows the request through if the JWT's
    role claim is 'admin'. Use alongside @jwt_required()."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        claims = get_jwt()
        if claims.get("role") != "admin":
            return jsonify({"error": "Admin access required"}), 403
        return fn(*args, **kwargs)
    return wrapper


def current_thresholds():
    """Reads block/review thresholds from the settings table (falls
    back to defaults if somehow missing)."""
    settings = database.get_all_settings()
    return {
        "block_threshold": float(settings.get("block_threshold", 70)),
        "review_threshold": float(settings.get("review_threshold", 35)),
    }


# ---------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------

@app.route("/")
def dashboard():
    return render_template("index.html")


@app.route("/login")
def login_page():
    return render_template("login.html")


@app.route("/admin")
def admin_page():
    return render_template("admin.html")


@app.route("/transaction/<txn_id>")
def transaction_detail_page(txn_id):
    return render_template("transaction_detail.html", txn_id=txn_id)


@app.route("/merchant/<merchant_id>")
def merchant_detail_page(merchant_id):
    return render_template("merchant_detail.html", merchant_id=merchant_id)


@app.route("/admin/users")
def user_management_page():
    return render_template("user_management.html")


@app.route("/profile")
def profile_page():
    return render_template("profile.html")


# ---------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------

@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "")
    role = data.get("role", "analyst")

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400
    if role not in ("analyst", "admin"):
        role = "analyst"

    try:
        auth.register_user(username, password, role)
    except ValueError as e:
        return jsonify({"error": str(e)}), 409

    return jsonify({"message": "User registered successfully"}), 201


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "")

    user = auth.authenticate(username, password)
    if not user:
        return jsonify({"error": "Invalid username or password"}), 401

    token = create_access_token(
        identity=username,
        additional_claims={"role": user["role"]},
    )
    return jsonify({"access_token": token, "role": user["role"], "username": username})


# ---------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------

def _score_and_store(features, txn_id, merchant_id):
    result = risk_model.score_transaction(ML_MODEL, features, current_thresholds())
    database.save_scored_transaction(txn_id, merchant_id, features, result)
    _check_for_alert(merchant_id)
    return result


def _check_for_alert(merchant_id, last_n=None):
    last_n = last_n or Config.ALERT_LOOKBACK_TRANSACTIONS
    alert_threshold = float(database.get_setting("alert_threshold", Config.DEFAULT_ALERT_THRESHOLD))
    summary = database.get_recent_merchant_avg(merchant_id, last_n=last_n)
    avg_score = summary.get("avg_score")
    count = summary.get("n", 0)

    if avg_score is not None and count >= 5 and avg_score >= alert_threshold:
        database.create_alert(
            merchant_id=merchant_id,
            message=(
                f"Merchant {merchant_id}'s average risk score over its last "
                f"{count} transactions is {round(avg_score, 1)} — "
                "consider manual review."
            ),
            avg_risk_score=round(avg_score, 1),
        )


@app.route("/api/score-transaction", methods=["POST"])
def score_transaction():
    """
    Score a real transaction.

    Expected JSON body:
    {
        "txn_id": "T12345", "merchant_id": "M100", "amount": 4500,
        "hour_of_day": 14, "location_mismatch": 0, "new_device_flag": 1,
        "velocity_last_hour": 2, "amount_deviation_ratio": 1.2
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

    features = {
        "amount": data["amount"],
        "hour_of_day": data["hour_of_day"],
        "is_odd_hour": 1 if data["hour_of_day"] < 6 or data["hour_of_day"] > 23 else 0,
        "location_mismatch": data["location_mismatch"],
        "new_device_flag": data["new_device_flag"],
        "velocity_last_hour": data["velocity_last_hour"],
        "amount_deviation_ratio": data.get("amount_deviation_ratio", 1.0),
    }

    txn_id = data.get("txn_id", f"T{random.randint(100000, 999999)}")
    merchant_id = data.get("merchant_id", "UNKNOWN")

    result = _score_and_store(features, txn_id, merchant_id)
    return jsonify({"txn_id": txn_id, "merchant_id": merchant_id, **result})


@app.route("/api/simulate-transaction", methods=["POST"])
def simulate_transaction():
    """Generates one random transaction and scores it — powers the demo button."""
    if ML_MODEL is None:
        return jsonify({"error": "Model not trained yet"}), 500

    merchant_id = f"M{random.randint(100, 139)}"
    hour = random.randint(0, 23)
    amount = round(random.expovariate(1 / 3000), 2)
    typical_amount = random.choice([500, 1500, 3000, 8000, 20000])

    features = {
        "amount": amount,
        "hour_of_day": hour,
        "is_odd_hour": 1 if hour < 6 or hour > 23 else 0,
        "location_mismatch": random.choices([0, 1], weights=[75, 25])[0],
        "new_device_flag": random.choices([0, 1], weights=[80, 20])[0],
        "velocity_last_hour": random.choices([1, 2, 3, 5, 8], weights=[60, 20, 10, 7, 3])[0],
        "amount_deviation_ratio": round(amount / typical_amount, 2),
    }

    txn_id = f"T{random.randint(100000, 999999)}"
    result = _score_and_store(features, txn_id, merchant_id)

    return jsonify({"txn_id": txn_id, "merchant_id": merchant_id, **features, **result})


# ---------------------------------------------------------------------
# Feedback loop
# ---------------------------------------------------------------------

@app.route("/api/feedback", methods=["POST"])
@jwt_required()
def submit_feedback():
    """
    A reviewer confirms whether a flagged transaction was actually
    fraud or actually safe. Stored for later retraining.

    Body: { "txn_id": "T12345", "verdict": "confirmed_fraud" }
    """
    data = request.get_json()
    txn_id = data.get("txn_id")
    verdict = data.get("verdict")

    if verdict not in ("confirmed_fraud", "confirmed_safe"):
        return jsonify({"error": "verdict must be confirmed_fraud or confirmed_safe"}), 400

    reviewer = get_jwt_identity()
    database.save_feedback(txn_id, reviewer, verdict)

    return jsonify({"message": "Feedback recorded"}), 201


# ---------------------------------------------------------------------
# Admin-only: settings + retraining
# ---------------------------------------------------------------------

@app.route("/api/settings", methods=["GET"])
@jwt_required()
def get_settings():
    """Any logged-in user can VIEW current thresholds (read-only)."""
    return jsonify(database.get_all_settings())


@app.route("/api/settings", methods=["PUT"])
@jwt_required()
@admin_required
def update_settings():
    """Only admins can CHANGE thresholds.

    Body: { "block_threshold": 75, "review_threshold": 30, "alert_threshold": 60 }
    Any subset of these keys may be sent.
    """
    data = request.get_json()
    allowed_keys = {"block_threshold", "review_threshold", "alert_threshold"}

    updated = {}
    for key, value in data.items():
        if key in allowed_keys:
            database.update_setting(key, value)
            updated[key] = value

    return jsonify({"message": "Settings updated", "updated": updated})


@app.route("/api/trigger-retrain", methods=["POST"])
@jwt_required()
@admin_required
def trigger_retrain():
    """Admin-only: retrain the model using accumulated reviewer feedback,
    reload it into memory immediately so new scores use it right away."""
    global ML_MODEL

    result = retrainer.retrain_with_feedback()
    ML_MODEL = risk_model.load_model()

    return jsonify(result)


@app.route("/api/feedback-summary")
@jwt_required()
@admin_required
def feedback_summary():
    """Admin-only: how much feedback has been collected, for the admin panel."""
    return jsonify({"total_feedback": database.count_feedback()})


# ---------------------------------------------------------------------
# Dashboard data
# ---------------------------------------------------------------------

@app.route("/api/recent-transactions")
def recent_transactions():
    """
    Supports filtering and pagination:
      ?limit=25&page=1&merchant_id=M101&action=block
    """
    limit = request.args.get("limit", default=25, type=int)
    page = request.args.get("page", default=1, type=int)
    merchant_id = request.args.get("merchant_id") or None
    action = request.args.get("action") or None

    offset = (page - 1) * limit

    transactions = database.get_recent_transactions(
        limit=limit, offset=offset, merchant_id=merchant_id, action=action
    )
    total = database.count_transactions(merchant_id=merchant_id, action=action)

    return jsonify({
        "transactions": transactions,
        "total": total,
        "page": page,
        "total_pages": max(1, (total + limit - 1) // limit),
    })


@app.route("/api/export-transactions")
def export_transactions():
    """Downloads all scored transactions as a CSV file."""
    rows = database.get_all_transactions_for_export()

    output = io.StringIO()
    if rows:
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=trustscore_transactions.csv"},
    )


@app.route("/api/merchant-summary")
def merchant_summary():
    return jsonify(database.get_merchant_summary())


@app.route("/api/transaction/<txn_id>")
def transaction_detail(txn_id):
    """Full detail for one transaction, including feedback history —
    powers the transaction detail page's SHAP breakdown."""
    txn = database.get_transaction_by_id(txn_id)
    if not txn:
        return jsonify({"error": "Transaction not found"}), 404

    feedback_history = database.get_feedback_for_transaction(txn_id)
    return jsonify({"transaction": txn, "feedback_history": feedback_history})


@app.route("/api/merchant/<merchant_id>")
def merchant_detail(merchant_id):
    """Full transaction history and risk trend for one merchant —
    powers the merchant detail page."""
    transactions = database.get_transactions_by_merchant(merchant_id)
    trend = database.get_merchant_risk_over_time(merchant_id)
    avg_summary = database.get_recent_merchant_avg(merchant_id, last_n=1000)

    return jsonify({
        "merchant_id": merchant_id,
        "transactions": transactions,
        "trend": trend,
        "avg_risk_score": avg_summary.get("avg_score"),
        "total_transactions": avg_summary.get("n", 0),
    })


@app.route("/api/risk-by-hour")
def risk_by_hour():
    """Average risk score by hour of day, across all transactions —
    powers the "riskiest hours" chart on the dashboard."""
    return jsonify(database.get_risk_by_hour())


@app.route("/api/users")
@jwt_required()
@admin_required
def list_users():
    """Admin-only: list all accounts (no password hashes) for the
    user management page."""
    return jsonify(database.get_all_users())


@app.route("/api/users/<username>/role", methods=["PUT"])
@jwt_required()
@admin_required
def update_user_role(username):
    """Admin-only: change another user's role."""
    data = request.get_json()
    new_role = data.get("role")

    if new_role not in ("analyst", "admin"):
        return jsonify({"error": "role must be 'analyst' or 'admin'"}), 400

    if not database.get_user_by_username(username):
        return jsonify({"error": "User not found"}), 404

    database.update_user_role(username, new_role)
    return jsonify({"message": f"{username}'s role updated to {new_role}"})


@app.route("/api/profile")
@jwt_required()
def profile():
    """Basic account info + how much feedback this user has submitted."""
    username = get_jwt_identity()
    user = database.get_user_by_username(username)
    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify({
        "username": user["username"],
        "role": user["role"],
        "created_at": user["created_at"],
        "feedback_submitted": database.count_feedback_by_user(username),
    })


@app.route("/api/profile/password", methods=["PUT"])
@jwt_required()
def change_password():
    """Lets a logged-in user change their own password."""
    username = get_jwt_identity()
    data = request.get_json()
    old_password = data.get("old_password", "")
    new_password = data.get("new_password", "")

    if not new_password or len(new_password) < 6:
        return jsonify({"error": "New password must be at least 6 characters"}), 400

    success = auth.change_password(username, old_password, new_password)
    if not success:
        return jsonify({"error": "Current password is incorrect"}), 401

    return jsonify({"message": "Password updated successfully"})


@app.route("/api/risk-trend")
def risk_trend():
    """Chronological risk scores for the trend chart."""
    return jsonify(database.get_risk_trend())


@app.route("/api/action-distribution")
def action_distribution():
    """Allow/review/block counts for the distribution chart."""
    return jsonify(database.get_action_distribution())


@app.route("/api/alerts")
def alerts():
    return jsonify(database.get_recent_alerts())


@app.route("/api/model-metrics")
def model_metrics():
    try:
        return jsonify(risk_model.load_metrics())
    except FileNotFoundError:
        return jsonify({"error": "No metrics found. Run model.py first."}), 404


if __name__ == "__main__":
    app.run(debug=Config.FLASK_DEBUG, port=Config.PORT)
