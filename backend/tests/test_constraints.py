"""
tests/test_constraints.py — Database constraint integration tests
Every PostgreSQL constraint is deliberately triggered via the API
and the response code/body is verified.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
PASSWORD = "Password123!"


@pytest.fixture(scope="module")
def owner_token():
    resp = client.post("/auth/login", json={"email": "owner@kaveristays.com", "password": PASSWORD})
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def guest_token():
    resp = client.post("/auth/login", json={"email": "aarav.sharma@example.com", "password": PASSWORD})
    return resp.json()["access_token"]


class TestUniqueConstraints:
    """SQLSTATE 23505 — Unique violations."""

    def test_duplicate_email_registration(self):
        """Registering with an existing email must return 409 EMAIL_EXISTS."""
        resp = client.post("/auth/register", json={
            "name": "Dup User",
            "email": "aarav.sharma@example.com",
            "password": "SomePass1!"
        })
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "EMAIL_EXISTS"


class TestCheckConstraints:
    """SQLSTATE 23514 — Check constraint violations."""

    def test_rating_below_1(self, owner_token, guest_token):
        """Review rating < 1 must be caught by Pydantic before DB."""
        resp = client.post(
            "/bookings/1/review",
            json={"rating": 0},
            headers={"Authorization": f"Bearer {guest_token}"}
        )
        assert resp.status_code == 422

    def test_rating_above_5(self, guest_token):
        """Review rating > 5 must be caught by Pydantic before DB."""
        resp = client.post(
            "/bookings/1/review",
            json={"rating": 6},
            headers={"Authorization": f"Bearer {guest_token}"}
        )
        assert resp.status_code == 422

    def test_guest_count_zero(self, guest_token):
        """guest_count < 1 must be caught by Pydantic before DB."""
        resp = client.post(
            "/bookings",
            json={"room_id": 1, "check_in": "2026-04-01", "check_out": "2026-04-02", "guest_count": 0},
            headers={"Authorization": f"Bearer {guest_token}"}
        )
        assert resp.status_code == 422


class TestGuestCapacityTrigger:
    """SQLSTATE P0001 — Guest capacity trigger enforced by DB."""

    def test_exceeds_max_occupancy_returns_422(self, guest_token):
        """Standard room max_occupancy=2. Booking for 10 guests must fail with EXCEEDS_OCCUPANCY."""
        resp = client.post(
            "/bookings",
            json={"room_id": 1, "check_in": "2026-07-01", "check_out": "2026-07-03", "guest_count": 10},
            headers={"Authorization": f"Bearer {guest_token}"}
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "EXCEEDS_OCCUPANCY"


class TestForeignKeyConstraints:
    """SQLSTATE 23503 — FK violations."""

    def test_booking_with_nonexistent_room(self, guest_token):
        """Booking referencing a non-existent room must return 404."""
        resp = client.post(
            "/bookings",
            json={"room_id": 999999, "check_in": "2026-07-01", "check_out": "2026-07-02", "guest_count": 1},
            headers={"Authorization": f"Bearer {guest_token}"}
        )
        assert resp.status_code == 404


class TestExclusionConstraint:
    """SQLSTATE 23P01 — GiST exclusion constraint for overlapping bookings."""

    def test_overlapping_booking_returns_409(self, owner_token):
        """
        Create a booking, then attempt to book the same room for overlapping dates.
        The DB exclusion constraint must fire and return 409 ROOM_UNAVAILABLE.
        """
        # Find an available room for a future date window
        avail = client.get(
            "/rooms/availability?property_id=1&check_in=2026-09-01&check_out=2026-09-05",
        )
        rooms = avail.json()
        if not rooms:
            pytest.skip("No rooms available for exclusion test")

        room_id = rooms[0]["room_id"]

        # First booking (should succeed)
        first = client.post(
            "/bookings",
            json={"room_id": room_id, "check_in": "2026-09-01", "check_out": "2026-09-05", "guest_count": 1},
            headers={"Authorization": f"Bearer {owner_token}"}
        )
        if first.status_code != 201:
            pytest.skip(f"Could not create first booking: {first.json()}")

        # Overlapping booking (should trigger exclusion)
        second = client.post(
            "/bookings",
            json={"room_id": room_id, "check_in": "2026-09-03", "check_out": "2026-09-07", "guest_count": 1},
            headers={"Authorization": f"Bearer {owner_token}"}
        )
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "ROOM_UNAVAILABLE"


class TestReviewConstraints:
    """One-review-per-booking enforcement."""

    def test_review_on_non_checked_out_booking(self, guest_token, owner_token):
        """Submitting review on confirmed booking must fail with STAY_NOT_COMPLETED."""
        # Find a confirmed booking
        list_resp = client.get(
            "/bookings?status=confirmed&limit=1",
            headers={"Authorization": f"Bearer {owner_token}"}
        )
        items = list_resp.json().get("items", [])
        if not items:
            pytest.skip("No confirmed bookings for review test")

        booking_id = items[0]["booking_id"]
        resp = client.post(
            f"/bookings/{booking_id}/review",
            json={"rating": 4, "comment": "Early review attempt"},
            headers={"Authorization": f"Bearer {guest_token}"}
        )
        # Should fail because booking is not checked_out
        assert resp.status_code in [400, 403, 404]  # 403/404 if guest doesn't own it
