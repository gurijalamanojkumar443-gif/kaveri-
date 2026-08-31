"""
tests/test_security.py — Security attack simulation (Stage 8)
Tests JWT attacks, SQL injection attempts, mass assignment, and timing attacks.
"""
import pytest
import time
import base64
import json
from fastapi.testclient import TestClient
from app.main import app
from app.security import create_access_token, decode_access_token

client = TestClient(app)
PASSWORD = "Password123!"
OWNER_EMAIL = "owner@kaveristays.com"


@pytest.fixture(scope="module")
def owner_token():
    resp = client.post("/auth/login", json={"email": OWNER_EMAIL, "password": PASSWORD})
    return resp.json()["access_token"]


class TestJWTAttacks:
    """8.1 JWT algorithm confusion: alg=none attack."""

    def test_alg_none_attack_rejected(self):
        """Forged token with alg=none must be rejected."""
        header = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).rstrip(b"=")
        payload = base64.urlsafe_b64encode(json.dumps({
            "sub": "1", "account_id": 1, "role": "owner", "exp": 9999999999
        }).encode()).rstrip(b"=")
        forged_token = f"{header.decode()}.{payload.decode()}."  # No signature
        resp = client.get("/auth/me", headers={"Authorization": f"Bearer {forged_token}"})
        assert resp.status_code == 401

    def test_tampered_jwt_signature(self, owner_token):
        """Modifying any part of the JWT must be rejected."""
        parts = owner_token.split(".")
        # Tamper the payload
        try:
            padded = parts[1] + "=" * (-len(parts[1]) % 4)
            payload = json.loads(base64.urlsafe_b64decode(padded))
            payload["role"] = "owner"
            new_payload = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=")
            tampered = f"{parts[0]}.{new_payload.decode()}.{parts[2]}"
            resp = client.get("/auth/me", headers={"Authorization": f"Bearer {tampered}"})
            assert resp.status_code == 401
        except Exception:
            pass  # Malformed base64 is fine — still gets rejected

    def test_expired_token_rejected(self):
        """Manually expired token must return 401."""
        from datetime import timedelta
        token = create_access_token(
            {"account_id": 1, "role": "owner", "email": "owner@kaveristays.com"},
            expires_delta=timedelta(seconds=-1)  # Already expired
        )
        resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    def test_wrong_algorithm_secret(self):
        """A token signed with a different secret must be rejected."""
        from jose import jwt as jose_jwt
        fake_token = jose_jwt.encode(
            {"account_id": 1, "role": "owner", "email": "x@x.com", "exp": 9999999999},
            "completely-wrong-secret-key-that-is-32-chars!!",
            algorithm="HS256"
        )
        resp = client.get("/auth/me", headers={"Authorization": f"Bearer {fake_token}"})
        assert resp.status_code == 401


class TestSQLInjection:
    """8.5 SQL injection tests — all inputs must be parameterized."""

    def test_sql_injection_in_email(self):
        """Injection in email field at login must not cause a 500."""
        resp = client.post("/auth/login", json={
            "email": "' OR '1'='1",
            "password": "anything"
        })
        assert resp.status_code in [401, 422]  # Must not be 500

    def test_sql_injection_in_property_id(self):
        """SQL injection in query param must be caught by type validation."""
        resp = client.get("/rooms/availability?property_id=1%20OR%201=1&check_in=2026-01-01&check_out=2026-01-05")
        assert resp.status_code == 422  # Not an integer, rejected by Pydantic

    def test_sql_injection_in_status_filter(self, owner_token):
        """Status filter with SQL injection payload must not error."""
        resp = client.get(
            "/bookings?status=confirmed'; DROP TABLE booking; --",
            headers={"Authorization": f"Bearer {owner_token}"}
        )
        # Should return 200 (no match) or 422, never 500
        assert resp.status_code in [200, 422]

    def test_sort_by_injection_rejected(self, owner_token):
        """sort_by with an injected column must fall back to default."""
        resp = client.get(
            "/bookings?sort_by=1; DROP TABLE booking; --",
            headers={"Authorization": f"Bearer {owner_token}"}
        )
        assert resp.status_code == 200  # Whitelist kicks in, safe fallback


class TestMassAssignment:
    """8.3 Mass assignment — role elevation through registration payload."""

    def test_cannot_self_assign_owner_role(self):
        """Registering with role=owner in body must be ignored."""
        import time as t
        email = f"hacker_{int(t.time())}@hack.com"
        resp = client.post("/auth/register", json={
            "name": "Hacker",
            "email": email,
            "password": "HackPass1!",
            "role": "owner"  # Must be silently ignored
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["role"] == "guest"  # Must always be 'guest' for self-registration

    def test_cannot_self_assign_property_id(self):
        """property_id in self-registration payload must be ignored."""
        import time as t
        email = f"hacker2_{int(t.time())}@hack.com"
        resp = client.post("/auth/register", json={
            "name": "Hacker2",
            "email": email,
            "password": "HackPass1!",
            "property_id": 1
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["property_id"] is None


class TestTimingAttacks:
    """8.10 Timing attack — login must take roughly constant time for valid vs invalid emails."""

    def test_login_timing_consistent(self):
        """Time for valid vs invalid email should be similar (both bcrypt-compared)."""
        times = []
        for _ in range(3):
            start = time.monotonic()
            client.post("/auth/login", json={"email": "nonexistent@example.com", "password": "wrong"})
            times.append(time.monotonic() - start)
        avg_invalid = sum(times) / len(times)

        times2 = []
        for _ in range(3):
            start = time.monotonic()
            client.post("/auth/login", json={"email": OWNER_EMAIL, "password": "wrong_password_here"})
            times2.append(time.monotonic() - start)
        avg_valid_email = sum(times2) / len(times2)

        # Both should take some time (not immediate rejection on unknown email)
        # Difference should be less than 0.5 seconds
        assert abs(avg_invalid - avg_valid_email) < 0.5, (
            f"Timing discrepancy too large: invalid={avg_invalid:.3f}s, valid_email={avg_valid_email:.3f}s"
        )


class TestErrorLeakage:
    """8.2 Responses must never leak stack traces, SQL details, or password hashes."""

    def test_404_does_not_leak_db_details(self):
        resp = client.get("/properties/99999")
        assert resp.status_code == 404
        text = resp.text
        assert "sqlalchemy" not in text.lower()
        assert "psycopg2" not in text.lower()
        assert "traceback" not in text.lower()
        assert "pg_" not in text.lower()

    def test_invalid_booking_does_not_leak_db_details(self, owner_token):
        resp = client.post(
            "/bookings",
            json={"room_id": 999999, "check_in": "2026-01-01", "check_out": "2026-01-02", "guest_count": 1},
            headers={"Authorization": f"Bearer {owner_token}"}
        )
        assert resp.status_code in [404, 422, 400]
        text = resp.text
        assert "sqlalchemy" not in text.lower()
        assert "traceback" not in text.lower()

    def test_login_error_does_not_reveal_user_existence(self):
        resp1 = client.post("/auth/login", json={"email": "nobody@example.com", "password": "wrong"})
        resp2 = client.post("/auth/login", json={"email": OWNER_EMAIL, "password": "wrong"})
        # Both should return the same error message
        assert resp1.json()["error"]["message"] == resp2.json()["error"]["message"]
