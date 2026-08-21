import sqlite3
from contextlib import contextmanager

DB_PATH = "trustscore.db"


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # lets us access columns by name
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
                txn_id TEXT,
                merchant_id TEXT,
                amount REAL,
                hour_of_day INTEGER,
                location_mismatch INTEGER,
                new_device_flag INTEGER,
                velocity_last_hour INTEGER,
                risk_score REAL,
                recommended_action TEXT,
                reasons TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)


def save_scored_transaction(txn_id, merchant_id, features, result):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO scored_transactions (
                txn_id, merchant_id, amount, hour_of_day,
                location_mismatch, new_device_flag, velocity_last_hour,
                risk_score, recommended_action, reasons
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            txn_id,
            merchant_id,
            features["amount"],
            features["hour_of_day"],
            features["location_mismatch"],
            features["new_device_flag"],
            features["velocity_last_hour"],
            result["risk_score"],
            result["recommended_action"],
            " | ".join(result["reasons"]),
        ))


def get_recent_transactions(limit=50):
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT * FROM scored_transactions
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()
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
