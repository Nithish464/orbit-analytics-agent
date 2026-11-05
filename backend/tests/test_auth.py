
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app import database


@pytest.fixture
def auth_client(tmp_path, monkeypatch):
    """
    Create an isolated test database and FastAPI client
    for every authentication test.
    """

    test_db = tmp_path / "orbit_auth_test.db"

    monkeypatch.setattr(
        database,
        "DB_PATH",
        test_db,
    )

    monkeypatch.setenv(
        "ORBIT_SECRET_KEY",
        "test-secret-key-for-orbit-auth-testing-123456",
    )

    with TestClient(app) as client:
        yield client


def register_user(
    client,
    email="orbit.test@example.com",
    password="OrbitSecure@2026",
):
    return client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": password,
        },
    )


# ============================================================
# REGISTRATION TESTS
# ============================================================

def test_user_registration_success(auth_client):
    response = register_user(auth_client)

    assert response.status_code == 201

    data = response.json()

    assert data["message"] == "Registration successful."
    assert data["token_type"] == "bearer"
    assert data["access_token"]

    assert data["user"]["email"] == "orbit.test@example.com"
    assert data["user"]["role"] == "user"
    assert data["user"]["is_active"] is True

    assert "password_hash" not in data["user"]


def test_duplicate_email_registration_rejected(auth_client):
    first_response = register_user(auth_client)

    second_response = register_user(auth_client)

    assert first_response.status_code == 201
    assert second_response.status_code == 400

    assert (
        second_response.json()["detail"]
        == "An account with this email already exists."
    )


def test_registration_rejects_short_password(auth_client):
    response = register_user(
        auth_client,
        password="Short123",
    )

    assert response.status_code == 422


def test_registration_rejects_invalid_email(auth_client):
    response = register_user(
        auth_client,
        email="invalid-email",
    )

    assert response.status_code == 400


# ============================================================
# LOGIN TESTS
# ============================================================

def test_user_login_success(auth_client):
    register_response = register_user(auth_client)

    assert register_response.status_code == 201

    response = auth_client.post(
        "/api/auth/login",
        json={
            "email": "orbit.test@example.com",
            "password": "OrbitSecure@2026",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["message"] == "Login successful."
    assert data["token_type"] == "bearer"
    assert data["access_token"]
    assert data["user"]["email"] == "orbit.test@example.com"

    assert "password_hash" not in data["user"]


def test_login_rejects_wrong_password(auth_client):
    register_user(auth_client)

    response = auth_client.post(
        "/api/auth/login",
        json={
            "email": "orbit.test@example.com",
            "password": "WrongPassword@2026",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Invalid email or password."
    )


def test_login_rejects_unknown_email(auth_client):
    response = auth_client.post(
        "/api/auth/login",
        json={
            "email": "unknown@example.com",
            "password": "OrbitSecure@2026",
        },
    )

    assert response.status_code == 401


# ============================================================
# JWT AND PROTECTED ROUTE TESTS
# ============================================================

def test_authenticated_user_can_access_profile(auth_client):
    register_response = register_user(auth_client)

    token = register_response.json()["access_token"]

    response = auth_client.get(
        "/api/auth/me",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200

    user = response.json()["user"]

    assert user["email"] == "orbit.test@example.com"
    assert user["role"] == "user"
    assert "password_hash" not in user


def test_profile_rejects_missing_token(auth_client):
    response = auth_client.get("/api/auth/me")

    assert response.status_code == 401


def test_profile_rejects_invalid_token(auth_client):
    response = auth_client.get(
        "/api/auth/me",
        headers={
            "Authorization": "Bearer invalid.jwt.token",
        },
    )

    assert response.status_code == 401


def test_profile_rejects_nonexistent_user_token(auth_client):
    from app.auth import create_access_token

    token = create_access_token(99999)

    response = auth_client.get(
        "/api/auth/me",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 401


# ============================================================
# ROLE-BASED AUTHORIZATION TESTS
# ============================================================

def test_normal_user_cannot_access_admin_endpoint(auth_client):
    register_response = register_user(auth_client)

    token = register_response.json()["access_token"]

    response = auth_client.get(
        "/api/auth/admin",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 403

    assert response.json()["detail"] == (
        "You do not have permission to access this resource."
    )


def test_admin_can_access_admin_endpoint(
    auth_client,
    monkeypatch,
):
    register_response = register_user(auth_client)

    token = register_response.json()["access_token"]

    # Promote the test account directly in the isolated test DB.
    connection = database.get_connection(readonly=False)

    try:
        connection.execute(
            """
            UPDATE users
            SET role = 'admin'
            WHERE email = ?
            """,
            ("orbit.test@example.com",),
        )

        connection.commit()

    finally:
        connection.close()

    response = auth_client.get(
        "/api/auth/admin",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Admin access granted."
    assert response.json()["user"]["role"] == "admin"


# ============================================================
# INACTIVE USER TEST
# ============================================================

def test_inactive_user_cannot_login(auth_client):
    register_response = register_user(auth_client)

    assert register_response.status_code == 201

    connection = database.get_connection(readonly=False)

    try:
        connection.execute(
            """
            UPDATE users
            SET is_active = 0
            WHERE email = ?
            """,
            ("orbit.test@example.com",),
        )

        connection.commit()

    finally:
        connection.close()

    response = auth_client.post(
        "/api/auth/login",
        json={
            "email": "orbit.test@example.com",
            "password": "OrbitSecure@2026",
        },
    )

    assert response.status_code == 401
