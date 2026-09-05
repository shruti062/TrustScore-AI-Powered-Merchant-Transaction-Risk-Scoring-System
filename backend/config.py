"""
config.py

Centralizes all configuration in one place instead of scattering
hardcoded values through app.py. Values are read from environment
variables (with sensible defaults for local development) so secrets
never need to live in source code.

For local development, copy .env.example to .env and fill in real
values — python-dotenv (loaded below) will pick it up automatically.
"""

import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()  # reads a .env file in the current directory, if present


class Config:
    JWT_SECRET_KEY = os.environ.get(
        "JWT_SECRET_KEY", "trustscore-dev-secret-change-this-in-production"
    )
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        hours=int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRES_HOURS", 8))
    )

    FLASK_DEBUG = os.environ.get("FLASK_DEBUG", "True") == "True"
    PORT = int(os.environ.get("PORT", 5000))

    # Default risk thresholds — actual live values are stored in the
    # database `settings` table and are admin-adjustable; these are
    # only the fallback values used the very first time the app runs.
    DEFAULT_BLOCK_THRESHOLD = 70
    DEFAULT_REVIEW_THRESHOLD = 35
    DEFAULT_ALERT_THRESHOLD = 55

    # How many of a merchant's most recent transactions to average
    # when checking whether to raise a risk alert
    ALERT_LOOKBACK_TRANSACTIONS = 10
