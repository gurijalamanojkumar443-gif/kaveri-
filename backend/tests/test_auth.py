import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import Account, RefreshToken
from app.security import hash_password

client = TestClient(app)

OWNER_EMAIL = "owner@kaveristays.com"
MANAGER_EMAIL = "manager.coorg@kaveristays.com"
STAFF_EMAIL = "staff.coorg@kaveristays.com"
GUEST_EMAIL = "aarav.sharma@example.com"
PASSWORD = "Password123!"


@pytest.fixture(scope="module")
def owner_token():
    resp = client.post("/auth/login", json={"email": OWNER_EMAIL, "password": PASSWORD})
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def manager_token():
    resp = client.post("/auth/login", json={"email": MANAGER_EMAIL, "password": PASSWORD})
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def staff_token():
    resp = client.post("/auth/login", json={"email": STAFF_EMAIL, "password": PASSWORD})
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def guest_token():
    resp = client.post("/auth/login", json={"email": GUEST_EMAIL, "password": PASSWORD})
    assert resp.status_code == 200
    return resp.json()["access_token"]


class TestRegister:
    def test_register_new_guest(self):
        import time
        email = f"new_test_{int(time.time())}@example.com"
        resp = client.post("/auth/register", json={
            "name": "New Test Guest",
            "email": email,
            "password": "SecurePass1!"
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["role"] == "guest"
        assert data["email"] == email
        assert "password" not in data
        assert "password_hash" not in data

    def test_register_duplicate_email(self):
        resp = client.post("/auth/register", json={
            "name": "Duplicate",
            "email": GUEST_EMAIL,
            "password": "AnyPassword1!"
        })
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "EMAIL_EXISTS"

    def test_register_short_password(self):
        resp = client.post("/auth/register", json={
            "name": "Bad Password",
            "email": "badpw@example.com",
            "password": "short"
        })
        assert resp.status_code == 422

    def test_register_invalid_email(self):
        resp = client.post("/auth/register", json={
            "name": "Bad Email",
            "email": "not-an-email",
            "password": "SecurePass1!"
        })
        assert resp.status_code == 422


class TestLogin:
    def test_login_success(self):
        resp = client.post("/auth/login", json={"email": OWNER_EMAIL, "password": PASSWORD})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self):
        resp = client.post("/auth/login", json={"email": OWNER_EMAIL, "password": "WrongPassword!"})
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"

    def test_login_nonexistent_email(self):
        resp = client.post("/auth/login", json={"email": "nobody@example.com", "password": "anything"})
        assert resp.status_code == 401

    def test_login_response_never_contains_hash(self):
        resp = client.post("/auth/login", json={"email": OWNER_EMAIL, "password": PASSWORD})
        text = resp.text.lower()
        assert "password_hash" not in text
        assert "$2b$" not in text


class TestRefreshToken:
    def test_refresh_token_rotation(self):
        login_resp = client.post("/auth/login", json={"email": OWNER_EMAIL, "password": PASSWORD})
        refresh = login_resp.json()["refresh_token"]

        # Use refresh token
        resp = client.post("/auth/refresh", json={"refresh_token": refresh})
        assert resp.status_code == 200
        new_data = resp.json()
        assert "access_token" in new_data
        assert new_data["refresh_token"] != refresh  # Token was rotated

    def test_refresh_token_reuse_attack(self):
        login_resp = client.post("/auth/login", json={"email": OWNER_EMAIL, "password": PASSWORD})
        refresh = login_resp.json()["refresh_token"]

        # Use refresh token once (legitimate)
        client.post("/auth/refresh", json={"refresh_token": refresh})

        # Reuse should trigger detection
        resp2 = client.post("/auth/refresh", json={"refresh_token": refresh})
        assert resp2.status_code == 401
        assert resp2.json()["error"]["code"] == "TOKEN_REVOKED"

    def test_invalid_refresh_token(self):
        resp = client.post("/auth/refresh", json={"refresh_token": "totally-invalid-token-xyz"})
        assert resp.status_code == 401


class TestMe:
    def test_me_requires_auth(self):
        resp = client.get("/auth/me")
        assert resp.status_code == 401

    def test_me_returns_correct_user(self, owner_token):
        resp = client.get("/auth/me", headers={"Authorization": f"Bearer {owner_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "owner"
        assert "password" not in data
        assert "password_hash" not in data

    def test_me_guest_fields(self, guest_token):
        resp = client.get("/auth/me", headers={"Authorization": f"Bearer {guest_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "guest"


class TestLogout:
    def test_logout_revokes_refresh_token(self):
        login = client.post("/auth/login", json={"email": GUEST_EMAIL, "password": PASSWORD})
        tokens = login.json()
        access = tokens["access_token"]
        refresh = tokens["refresh_token"]

        logout = client.post(
            "/auth/logout",
            json={"refresh_token": refresh},
            headers={"Authorization": f"Bearer {access}"}
        )
        assert logout.status_code == 200

        # After logout, refresh should fail
        retry = client.post("/auth/refresh", json={"refresh_token": refresh})
        assert retry.status_code == 401
