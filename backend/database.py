
import sqlite3
from contextlib import contextmanager
from config import Config

DB_PATH = "trustscore.db"

DEFAULT_SETTINGS = {
    "block_threshold": str(Config.DEFAULT_BLOCK_THRESHOLD),
    "review_threshold": str(Config.DEFAULT_REVIEW_THRESHOLD),
    "alert_threshold": str(Config.DEFAULT_ALERT_THRESHOLD),
}


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scored_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                txn_id TEXT UNIQUE,
                merchant_id TEXT,
                amount REAL,
                hour_of_day INTEGER,
                location_mismatch INTEGER,
                new_device_flag INTEGER,
                velocity_last_hour INTEGER,
                amount_deviation_ratio REAL,
                risk_score REAL,
                recommended_action TEXT,
                reasons TEXT,
                top_contributing_features TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password_hash TEXT,
                role TEXT DEFAULT 'analyst',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                txn_id TEXT,
                reviewer_username TEXT,
                verdict TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                merchant_id TEXT,
                message TEXT,
                avg_risk_score REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # Seed default settings only if they don't already exist,
        # so we never overwrite an admin's saved changes on restart
        for key, value in DEFAULT_SETTINGS.items():
            conn.execute("""
                INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)
            """, (key, value))


# ---------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------

def save_scored_transaction(txn_id, merchant_id, features, result):
    with get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO scored_transactions (
                txn_id, merchant_id, amount, hour_of_day,
                location_mismatch, new_device_flag, velocity_last_hour,
                amount_deviation_ratio, risk_score, recommended_action,
                reasons, top_contributing_features
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            txn_id, merchant_id,
            features["amount"], features["hour_of_day"],
            features["location_mismatch"], features["new_device_flag"],
            features["velocity_last_hour"], features["amount_deviation_ratio"],
            result["risk_score"], result["recommended_action"],
            " | ".join(result["reasons"]),
            str(result.get("top_contributing_features", [])),
        ))


def get_recent_transactions(limit=25, offset=0, merchant_id=None, action=None):
    """
    Fetch scored transactions, newest first, with optional filtering
    by merchant and/or recommended action, and pagination via
    limit/offset.
    """
    query = "SELECT * FROM scored_transactions WHERE 1=1"
    params = []

    if merchant_id:
        query += " AND merchant_id = ?"
        params.append(merchant_id)
    if action:
        query += " AND recommended_action = ?"
        params.append(action)

    query += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


def count_transactions(merchant_id=None, action=None):
    """Total matching row count — used to compute total pages for pagination."""
    query = "SELECT COUNT(*) as cnt FROM scored_transactions WHERE 1=1"
    params = []
    if merchant_id:
        query += " AND merchant_id = ?"
        params.append(merchant_id)
    if action:
        query += " AND recommended_action = ?"
        params.append(action)

    with get_connection() as conn:
        row = conn.execute(query, params).fetchone()
        return row["cnt"]


def get_all_transactions_for_export():
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT txn_id, merchant_id, amount, hour_of_day, risk_score,
                   recommended_action, reasons, created_at
            FROM scored_transactions ORDER BY id DESC
        """).fetchall()
        return [dict(row) for row in rows]


def get_merchant_summary():
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT
                merchant_id,
                COUNT(*) AS total_transactions,
                ROUND(AVG(risk_score), 1) AS avg_risk_score,
                SUM(CASE WHEN recommended_action != 'allow' THEN 1 ELSE 0 END) AS flagged_count
            FROM scored_transactions
            GROUP BY merchant_id
            ORDER BY avg_risk_score DESC
        """).fetchall()
        return [dict(row) for row in rows]


def get_recent_merchant_avg(merchant_id, last_n=10):
    with get_connection() as conn:
        row = conn.execute("""
            SELECT AVG(risk_score) AS avg_score, COUNT(*) AS n
            FROM (
                SELECT risk_score FROM scored_transactions
                WHERE merchant_id = ?
                ORDER BY id DESC LIMIT ?
            )
        """, (merchant_id, last_n)).fetchone()
        return dict(row) if row else {"avg_score": None, "n": 0}


def get_risk_trend(limit=40):
    """
    Returns risk scores in chronological order (oldest to newest) for
    the trend chart on the dashboard.
    """
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT txn_id, risk_score, created_at FROM (
                SELECT * FROM scored_transactions ORDER BY id DESC LIMIT ?
            ) ORDER BY id ASC
        """, (limit,)).fetchall()
        return [dict(row) for row in rows]


def get_action_distribution():
    """Allow/review/block counts — powers the distribution chart."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT recommended_action, COUNT(*) as count
            FROM scored_transactions
            GROUP BY recommended_action
        """).fetchall()
        return {row["recommended_action"]: row["count"] for row in rows}


def get_transaction_by_id(txn_id):
    """Full detail for a single transaction — powers the transaction detail page."""
    with get_connection() as conn:
        row = conn.execute("""
            SELECT * FROM scored_transactions WHERE txn_id = ?
        """, (txn_id,)).fetchone()
        return dict(row) if row else None


def get_feedback_for_transaction(txn_id):
    """All feedback submitted for one transaction, newest first."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT * FROM feedback WHERE txn_id = ? ORDER BY id DESC
        """, (txn_id,)).fetchall()
        return [dict(row) for row in rows]


def get_transactions_by_merchant(merchant_id, limit=100):
    """A merchant's transaction history, newest first — powers the merchant detail page."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT * FROM scored_transactions
            WHERE merchant_id = ?
            ORDER BY id DESC LIMIT ?
        """, (merchant_id, limit)).fetchall()
        return [dict(row) for row in rows]


def get_merchant_risk_over_time(merchant_id, limit=40):
    """Chronological risk scores for one merchant — powers its trend chart."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT txn_id, risk_score, created_at FROM (
                SELECT * FROM scored_transactions
                WHERE merchant_id = ?
                ORDER BY id DESC LIMIT ?
            ) ORDER BY id ASC
        """, (merchant_id, limit)).fetchall()
        return [dict(row) for row in rows]


def get_risk_by_hour():
    """
    Average risk score grouped by hour of day (0-23), across all
    merchants — powers the "riskiest hours" chart on the dashboard.
    """
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT hour_of_day, ROUND(AVG(risk_score), 1) AS avg_risk_score, COUNT(*) AS count
            FROM scored_transactions
            GROUP BY hour_of_day
            ORDER BY hour_of_day ASC
        """).fetchall()
        return [dict(row) for row in rows]


# ---------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------

def create_user(username, password_hash, role="analyst"):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO users (username, password_hash, role)
            VALUES (?, ?, ?)
        """, (username, password_hash, role))


def get_user_by_username(username):
    with get_connection() as conn:
        row = conn.execute("""
            SELECT * FROM users WHERE username = ?
        """, (username,)).fetchone()
        return dict(row) if row else None


def get_all_users():
    """All accounts (without password hashes) — powers the admin user management page."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id, username, role, created_at FROM users ORDER BY id ASC
        """).fetchall()
        return [dict(row) for row in rows]


def update_user_password(username, new_password_hash):
    with get_connection() as conn:
        conn.execute("""
            UPDATE users SET password_hash = ? WHERE username = ?
        """, (new_password_hash, username))


def update_user_role(username, new_role):
    with get_connection() as conn:
        conn.execute("""
            UPDATE users SET role = ? WHERE username = ?
        """, (new_role, username))


# ---------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------

def save_feedback(txn_id, reviewer_username, verdict):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO feedback (txn_id, reviewer_username, verdict)
            VALUES (?, ?, ?)
        """, (txn_id, reviewer_username, verdict))


def get_all_feedback():
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT * FROM feedback ORDER BY id DESC
        """).fetchall()
        return [dict(row) for row in rows]


def count_feedback():
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) as cnt FROM feedback").fetchone()
        return row["cnt"]


def count_feedback_by_user(username):
    with get_connection() as conn:
        row = conn.execute("""
            SELECT COUNT(*) as cnt FROM feedback WHERE reviewer_username = ?
        """, (username,)).fetchone()
        return row["cnt"]


# ---------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------

def create_alert(merchant_id, message, avg_risk_score):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO alerts (merchant_id, message, avg_risk_score)
            VALUES (?, ?, ?)
        """, (merchant_id, message, avg_risk_score))


def get_recent_alerts(limit=20):
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT * FROM alerts ORDER BY id DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(row) for row in rows]


# ---------------------------------------------------------------------
# Settings (admin-configurable values)
# ---------------------------------------------------------------------

def get_all_settings():
    with get_connection() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return {row["key"]: row["value"] for row in rows}


def get_setting(key, default=None):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default


def update_setting(key, value):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (key, str(value)))
