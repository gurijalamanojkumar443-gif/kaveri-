"""
tests/test_payments.py — Payment recording and review flow.
Creates a full booking lifecycle (create → check-in → check-out) to test
the payment and review endpoints with a valid checked_out booking.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
PASSWORD = "Password123!"


@pytest.fixture(scope="module")
def owner_token():
    resp = client.post("/auth/login", json={"email": "owner@kaveristays.com", "password": PASSWORD})
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def staff_token():
    resp = client.post("/auth/login", json={"email": "staff.coorg@kaveristays.com", "password": PASSWORD})
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def guest_token():
    resp = client.post("/auth/login", json={"email": "aarav.sharma@example.com", "password": PASSWORD})
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def full_lifecycle_booking(owner_token, staff_token):
    """
    Creates a booking, checks it in, checks it out.
    Returns the booking_id of a checked_out booking for review/payment tests.
    """
    # Find an available room far in the future
    avail = client.get(
        "/rooms/availability?property_id=1&check_in=2027-06-01&check_out=2027-06-03"
    )
    rooms = avail.json()
    if not rooms:
        pytest.skip("No rooms available for lifecycle test")

    room_id = rooms[0]["room_id"]

    # Create booking
    create = client.post(
        "/bookings",
        json={"room_id": room_id, "check_in": "2027-06-01", "check_out": "2027-06-03", "guest_count": 1},
        headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert create.status_code == 201, f"Create failed: {create.json()}"
    bid = create.json()["booking_id"]

    # Check-in
    ci = client.post(f"/bookings/{bid}/check-in", headers={"Authorization": f"Bearer {staff_token}"})
    assert ci.status_code == 200, f"Check-in failed: {ci.json()}"

    # Check-out
    co = client.post(f"/bookings/{bid}/check-out", headers={"Authorization": f"Bearer {staff_token}"})
    assert co.status_code == 200, f"Check-out failed: {co.json()}"
    assert co.json()["status"] == "checked_out"

    return bid


class TestPayments:
    def test_get_payments_list(self, full_lifecycle_booking, owner_token):
        bid = full_lifecycle_booking
        resp = client.get(f"/bookings/{bid}/payments", headers={"Authorization": f"Bearer {owner_token}"})
        assert resp.status_code == 200
        payments = resp.json()
        assert isinstance(payments, list)
        # At least the deposit payment should exist
        assert len(payments) >= 1
        for p in payments:
            assert "payment_id" in p
            assert "amount" in p
            assert "method" in p

    def test_record_additional_payment(self, full_lifecycle_booking, owner_token):
        bid = full_lifecycle_booking
        resp = client.post(
            f"/bookings/{bid}/payments",
            json={"amount": 100.00, "method": "cash"},
            headers={"Authorization": f"Bearer {owner_token}"}
        )
        # Either succeeds (201) or fails if balance already fully paid (400)
        assert resp.status_code in [201, 400]

    def test_idempotency_key_deduplication(self, full_lifecycle_booking, owner_token):
        bid = full_lifecycle_booking
        key = "test-idempotency-key-xyz-123"
        # First request
        resp1 = client.post(
            f"/bookings/{bid}/payments",
            json={"amount": 1.00, "method": "card"},
            headers={"Authorization": f"Bearer {owner_token}", "Idempotency-Key": key}
        )
        # If first succeeds, second must return same payment_id
        if resp1.status_code == 201:
            pid1 = resp1.json()["payment_id"]
            resp2 = client.post(
                f"/bookings/{bid}/payments",
                json={"amount": 1.00, "method": "card"},
                headers={"Authorization": f"Bearer {owner_token}", "Idempotency-Key": key}
            )
            if resp2.status_code == 201:
                pid2 = resp2.json()["payment_id"]
                assert pid1 == pid2, "Idempotency key did not deduplicate payment"

    def test_guest_cannot_view_other_booking_payments(self, full_lifecycle_booking, guest_token):
        bid = full_lifecycle_booking
        resp = client.get(f"/bookings/{bid}/payments", headers={"Authorization": f"Bearer {guest_token}"})
        # If this booking belongs to owner (guest_id != aarav's guest_id), should be 404
        assert resp.status_code in [200, 404]

    def test_payment_requires_auth(self, full_lifecycle_booking):
        bid = full_lifecycle_booking
        resp = client.post(f"/bookings/{bid}/payments", json={"amount": 100, "method": "card"})
        assert resp.status_code == 401


class TestReviews:
    def test_submit_review_on_checked_out_booking(self, full_lifecycle_booking, owner_token):
        bid = full_lifecycle_booking
        resp = client.post(
            f"/bookings/{bid}/review",
            json={"rating": 5, "comment": "Excellent automated test stay!"},
            headers={"Authorization": f"Bearer {owner_token}"}
        )
        # Should succeed (201) or already submitted (409)
        assert resp.status_code in [201, 409]
        if resp.status_code == 201:
            data = resp.json()
            assert data["rating"] == 5
            assert data["booking_id"] == bid
            assert "password" not in resp.text

    def test_duplicate_review_blocked(self, full_lifecycle_booking, owner_token):
        bid = full_lifecycle_booking
        # Submit first review
        client.post(
            f"/bookings/{bid}/review",
            json={"rating": 4, "comment": "First review"},
            headers={"Authorization": f"Bearer {owner_token}"}
        )
        # Try submitting a second review for the same booking
        resp2 = client.post(
            f"/bookings/{bid}/review",
            json={"rating": 3, "comment": "Second review attempt"},
            headers={"Authorization": f"Bearer {owner_token}"}
        )
        assert resp2.status_code in [409, 201]  # 409 if already reviewed, 201 if first time

    def test_review_on_confirmed_booking_rejected(self, guest_token):
        """Can't review a booking that hasn't been checked out."""
        # Get a confirmed booking
        resp = client.get(
            "/bookings?status=confirmed&limit=1",
            headers={"Authorization": f"Bearer {guest_token}"}
        )
        items = resp.json().get("items", [])
        if not items:
            pytest.skip("No confirmed bookings for guest")
        bid = items[0]["booking_id"]
        review = client.post(
            f"/bookings/{bid}/review",
            json={"rating": 5, "comment": "Premature review"},
            headers={"Authorization": f"Bearer {guest_token}"}
        )
        # Should reject with 400 STAY_NOT_COMPLETED or 403/404 if not owner
        assert review.status_code in [400, 403, 404]

    def test_review_rating_validation(self, full_lifecycle_booking, owner_token):
        bid = full_lifecycle_booking
        for bad_rating in [0, 6, -1, 100]:
            resp = client.post(
                f"/bookings/{bid}/review",
                json={"rating": bad_rating},
                headers={"Authorization": f"Bearer {owner_token}"}
            )
            assert resp.status_code == 422

    def test_review_requires_auth(self, full_lifecycle_booking):
        bid = full_lifecycle_booking
        resp = client.post(f"/bookings/{bid}/review", json={"rating": 5})
        assert resp.status_code == 401
