"""
tests/test_api.py

End-to-end tests for the Flask API using Flask's built-in test
client — no need to actually run the server. Uses a temporary
database so these never touch real data.

Note: these tests need a trained model (risk_model.pkl) to exist,
since app.py loads it at import time. Run generate_data.py and
model.py before running this test file — the CI workflow does this
automatically (see .github/workflows/ci.yml).
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import database


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Spins up the Flask app with a throwaway database for each test."""
    db_file = tmp_path / "test_trustscore.db"
    monkeypatch.setattr(database, "DB_PATH", str(db_file))

    import app as flask_app_module
    flask_app_module.app.config["TESTING"] = True
    database.init_db()

    with flask_app_module.app.test_client() as test_client:
        yield test_client


def test_register_new_user_succeeds(client):
    response = client.post("/api/register", json={
        "username": "apitestuser", "password": "pass123"
    })
    assert response.status_code == 201


def test_register_duplicate_user_fails(client):
    client.post("/api/register", json={"username": "dupe", "password": "pass123"})
    response = client.post("/api/register", json={"username": "dupe", "password": "pass456"})
    assert response.status_code == 409


def test_register_missing_fields_fails(client):
    response = client.post("/api/register", json={"username": "onlyusername"})
    assert response.status_code == 400


def test_login_with_correct_credentials_returns_token(client):
    client.post("/api/register", json={"username": "loginuser", "password": "mypass"})
    response = client.post("/api/login", json={"username": "loginuser", "password": "mypass"})
    assert response.status_code == 200
    assert "access_token" in response.get_json()


def test_login_with_wrong_password_fails(client):
    client.post("/api/register", json={"username": "loginuser2", "password": "mypass"})
    response = client.post("/api/login", json={"username": "loginuser2", "password": "wrong"})
    assert response.status_code == 401


def test_feedback_requires_authentication(client):
    response = client.post("/api/feedback", json={
        "txn_id": "T12345", "verdict": "confirmed_fraud"
    })
    assert response.status_code == 401


def test_settings_update_requires_admin_role(client):
    client.post("/api/register", json={
        "username": "regularanalyst", "password": "pass123", "role": "analyst"
    })
    login = client.post("/api/login", json={
        "username": "regularanalyst", "password": "pass123"
    })
    token = login.get_json()["access_token"]

    response = client.put("/api/settings",
        json={"block_threshold": 90},
        headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_settings_update_succeeds_for_admin(client):
    client.post("/api/register", json={
        "username": "adminuser", "password": "pass123", "role": "admin"
    })
    login = client.post("/api/login", json={
        "username": "adminuser", "password": "pass123"
    })
    token = login.get_json()["access_token"]

    response = client.put("/api/settings",
        json={"block_threshold": 90},
        headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200


def test_recent_transactions_returns_paginated_shape(client):
    response = client.get("/api/recent-transactions?limit=5&page=1")
    assert response.status_code == 200
    data = response.get_json()
    assert "transactions" in data
    assert "total" in data
    assert "page" in data
    assert "total_pages" in data


def test_transaction_detail_returns_404_for_unknown_txn(client):
    response = client.get("/api/transaction/T_DOES_NOT_EXIST")
    assert response.status_code == 404


def test_merchant_detail_returns_shape_even_with_no_transactions(client):
    response = client.get("/api/merchant/M_NO_TRANSACTIONS")
    assert response.status_code == 200
    data = response.get_json()
    assert data["merchant_id"] == "M_NO_TRANSACTIONS"
    assert data["transactions"] == []
    assert data["total_transactions"] == 0


def test_risk_by_hour_returns_a_list(client):
    response = client.get("/api/risk-by-hour")
    assert response.status_code == 200
    assert isinstance(response.get_json(), list)


def test_list_users_requires_admin_role(client):
    client.post("/api/register", json={
        "username": "plainanalyst", "password": "pass123", "role": "analyst"
    })
    login = client.post("/api/login", json={"username": "plainanalyst", "password": "pass123"})
    token = login.get_json()["access_token"]

    response = client.get("/api/users", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_list_users_succeeds_for_admin(client):
    client.post("/api/register", json={
        "username": "adminlister", "password": "pass123", "role": "admin"
    })
    login = client.post("/api/login", json={"username": "adminlister", "password": "pass123"})
    token = login.get_json()["access_token"]

    response = client.get("/api/users", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    usernames = [u["username"] for u in response.get_json()]
    assert "adminlister" in usernames


def test_update_user_role_rejects_invalid_role(client):
    client.post("/api/register", json={
        "username": "roleadmin", "password": "pass123", "role": "admin"
    })
    client.post("/api/register", json={"username": "targetuser", "password": "pass123"})
    login = client.post("/api/login", json={"username": "roleadmin", "password": "pass123"})
    token = login.get_json()["access_token"]

    response = client.put("/api/users/targetuser/role",
        json={"role": "superuser"},
        headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 400


def test_profile_requires_authentication(client):
    response = client.get("/api/profile")
    assert response.status_code == 401


def test_profile_returns_own_account_info(client):
    client.post("/api/register", json={"username": "profileuser", "password": "pass123"})
    login = client.post("/api/login", json={"username": "profileuser", "password": "pass123"})
    token = login.get_json()["access_token"]

    response = client.get("/api/profile", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.get_json()["username"] == "profileuser"


def test_change_password_rejects_wrong_old_password(client):
    client.post("/api/register", json={"username": "pwuser", "password": "correctpass"})
    login = client.post("/api/login", json={"username": "pwuser", "password": "correctpass"})
    token = login.get_json()["access_token"]

    response = client.put("/api/profile/password",
        json={"old_password": "wrongpass", "new_password": "newpassword123"},
        headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_change_password_rejects_short_new_password(client):
    client.post("/api/register", json={"username": "pwuser2", "password": "correctpass"})
    login = client.post("/api/login", json={"username": "pwuser2", "password": "correctpass"})
    token = login.get_json()["access_token"]

    response = client.put("/api/profile/password",
        json={"old_password": "correctpass", "new_password": "abc"},
        headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 400


def test_change_password_succeeds_with_correct_old_password(client):
    client.post("/api/register", json={"username": "pwuser3", "password": "correctpass"})
    login = client.post("/api/login", json={"username": "pwuser3", "password": "correctpass"})
    token = login.get_json()["access_token"]

    response = client.put("/api/profile/password",
        json={"old_password": "correctpass", "new_password": "newpassword123"},
        headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200

    # confirm the new password actually works for login now
    relogin = client.post("/api/login", json={"username": "pwuser3", "password": "newpassword123"})
    assert relogin.status_code == 200
