"""
tests/test_auth.py

Tests for password hashing and authentication logic. Uses a temporary
SQLite database so tests never touch the real trustscore.db.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import database
import auth


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Points database.py at a throwaway SQLite file for this test only."""
    db_file = tmp_path / "test_trustscore.db"
    monkeypatch.setattr(database, "DB_PATH", str(db_file))
    database.init_db()
    yield db_file


def test_hash_password_produces_different_output_than_input():
    hashed = auth.hash_password("mypassword123")
    assert hashed != "mypassword123"
    assert len(hashed) > 20  # bcrypt hashes are long


def test_verify_password_correct_password_succeeds():
    hashed = auth.hash_password("correcthorse")
    assert auth.verify_password("correcthorse", hashed) is True


def test_verify_password_wrong_password_fails():
    hashed = auth.hash_password("correcthorse")
    assert auth.verify_password("wrongpassword", hashed) is False


def test_register_user_creates_account(temp_db):
    auth.register_user("newanalyst", "pass123", role="analyst")
    user = database.get_user_by_username("newanalyst")
    assert user is not None
    assert user["role"] == "analyst"


def test_register_user_duplicate_username_raises(temp_db):
    auth.register_user("duplicate", "pass123")
    with pytest.raises(ValueError):
        auth.register_user("duplicate", "differentpass")


def test_authenticate_correct_credentials(temp_db):
    auth.register_user("logintest", "mypassword")
    user = auth.authenticate("logintest", "mypassword")
    assert user is not None
    assert user["username"] == "logintest"


def test_authenticate_wrong_password_returns_none(temp_db):
    auth.register_user("logintest2", "mypassword")
    user = auth.authenticate("logintest2", "wrongpassword")
    assert user is None


def test_authenticate_nonexistent_user_returns_none(temp_db):
    user = auth.authenticate("doesnotexist", "anypassword")
    assert user is None
