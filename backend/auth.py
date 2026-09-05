"""
auth.py

Small authentication helper. Two roles exist:
  - "analyst" : can view the dashboard and submit feedback
  - "admin"   : same as analyst, plus can trigger retraining

Passwords are hashed with bcrypt before storage — we never store or
log a plain-text password.
"""

import bcrypt
import database


def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(plain_password.encode(), password_hash.encode())


def register_user(username: str, password: str, role: str = "analyst"):
    if database.get_user_by_username(username):
        raise ValueError("Username already exists")

    password_hash = hash_password(password)
    database.create_user(username, password_hash, role)


def authenticate(username: str, password: str):
    """Returns the user dict if credentials are valid, else None."""
    user = database.get_user_by_username(username)
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return user


def change_password(username: str, old_password: str, new_password: str) -> bool:
    """
    Changes a user's password after verifying the old one. Returns
    True on success, False if the old password didn't match.
    """
    user = database.get_user_by_username(username)
    if not user or not verify_password(old_password, user["password_hash"]):
        return False

    new_hash = hash_password(new_password)
    database.update_user_password(username, new_hash)
    return True
