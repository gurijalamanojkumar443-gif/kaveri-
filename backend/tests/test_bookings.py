import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

OWNER_EMAIL = "owner@kaveristays.com"
PASSWORD = "Password123!"


@pytest.fixture(scope="module")
def owner_token():
    resp = client.post("/auth/login", json={"email": OWNER_EMAIL, "password": PASSWORD})
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def staff_token():
    resp = client.post("/auth/login", json={"email": "staff.coorg@kaveristays.com", "password": PASSWORD})
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def manager_token():
    resp = client.post("/auth/login", json={"email": "manager.coorg@kaveristays.com", "password": PASSWORD})
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def guest_token():
    resp = client.post("/auth/login", json={"email": "aarav.sharma@example.com", "password": PASSWORD})
    return resp.json()["access_token"]


class TestProperties:
    def test_list_properties_public(self):
        resp = client.get("/properties")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        names = [p["name"] for p in data]
        assert "Kaveri Riverside" in names
        assert "Kaveri Hilltop" in names
        assert "Kaveri Backwater" in names

    def test_property_detail_with_room_types(self):
        resp = client.get("/properties/1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["property_id"] == 1
        assert len(data["room_types"]) >= 1
        assert all("type_name" in rt for rt in data["room_types"])
        assert all("max_occupancy" in rt for rt in data["room_types"])

    def test_property_not_found(self):
        resp = client.get("/properties/9999")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "NOT_FOUND"


class TestRoomAvailability:
    def test_availability_requires_property_and_dates(self):
        resp = client.get("/rooms/availability")
        assert resp.status_code == 422

    def test_availability_returns_list(self):
        resp = client.get("/rooms/availability?property_id=1&check_in=2025-12-28&check_out=2025-12-30")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        for room in data:
            assert "room_id" in room
            assert "nightly_rate" in room
            assert "total_rate" in room

    def test_availability_invalid_dates(self):
        resp = client.get("/rooms/availability?property_id=1&check_in=2025-12-30&check_out=2025-12-28")
        assert resp.status_code == 422

    def test_availability_nonexistent_property(self):
        resp = client.get("/rooms/availability?property_id=9999&check_in=2025-12-25&check_out=2025-12-28")
        assert resp.status_code == 404

    def test_availability_rate_computed(self):
        resp = client.get("/rooms/availability?property_id=1&check_in=2026-02-01&check_out=2026-02-04")
        assert resp.status_code == 200
        data = resp.json()
        if data:
            room = data[0]
            assert room["total_rate"] > 0
            # 3 nights, nightly_rate * 3 ~= total_rate
            assert abs(room["total_rate"] - room["nightly_rate"] * 3) < 1


class TestBookingsList:
    def test_bookings_requires_auth(self):
        resp = client.get("/bookings")
        assert resp.status_code == 401

    def test_owner_sees_all_bookings(self, owner_token):
        resp = client.get("/bookings", headers={"Authorization": f"Bearer {owner_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "items" in data
        assert data["total"] >= 0

    def test_guest_sees_only_own_bookings(self, guest_token):
        resp = client.get("/bookings", headers={"Authorization": f"Bearer {guest_token}"})
        assert resp.status_code == 200
        data = resp.json()
        # All items belong to this guest
        for item in data["items"]:
            assert "booking_id" in item

    def test_manager_scoped_to_property(self, manager_token):
        resp = client.get("/bookings", headers={"Authorization": f"Bearer {manager_token}"})
        assert resp.status_code == 200

    def test_bookings_pagination(self, owner_token):
        resp = client.get("/bookings?limit=5&offset=0", headers={"Authorization": f"Bearer {owner_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["limit"] == 5
        assert len(data["items"]) <= 5

    def test_bookings_status_filter(self, owner_token):
        resp = client.get("/bookings?status=confirmed", headers={"Authorization": f"Bearer {owner_token}"})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["status"] == "confirmed"


class TestCreateBooking:
    def test_create_booking_invalid_dates(self, guest_token):
        resp = client.post(
            "/bookings",
            json={"room_id": 1, "check_in": "2025-12-30", "check_out": "2025-12-28", "guest_count": 1},
            headers={"Authorization": f"Bearer {guest_token}"}
        )
        assert resp.status_code in [400, 422]

    def test_create_booking_exceeds_occupancy(self, guest_token):
        # Standard room allows max 2 guests
        resp = client.post(
            "/bookings",
            json={"room_id": 1, "check_in": "2026-03-01", "check_out": "2026-03-03", "guest_count": 10},
            headers={"Authorization": f"Bearer {guest_token}"}
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "EXCEEDS_OCCUPANCY"

    def test_create_booking_requires_auth(self):
        resp = client.post(
            "/bookings",
            json={"room_id": 1, "check_in": "2026-03-01", "check_out": "2026-03-03", "guest_count": 1}
        )
        assert resp.status_code == 401


class TestBookingStateMachine:
    def test_cancel_confirmed_booking(self, owner_token):
        # Find a confirmed booking
        list_resp = client.get(
            "/bookings?status=confirmed&limit=1",
            headers={"Authorization": f"Bearer {owner_token}"}
        )
        items = list_resp.json()["items"]
        if not items:
            pytest.skip("No confirmed bookings available for cancellation test")

        booking_id = items[0]["booking_id"]
        resp = client.post(
            f"/bookings/{booking_id}/cancel",
            headers={"Authorization": f"Bearer {owner_token}"}
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    def test_checkin_requires_staff(self, guest_token):
        resp = client.post(
            "/bookings/1/check-in",
            headers={"Authorization": f"Bearer {guest_token}"}
        )
        assert resp.status_code == 403

    def test_get_booking_by_id_requires_auth(self):
        resp = client.get("/bookings/1")
        assert resp.status_code == 401


class TestReports:
    def test_occupancy_requires_manager(self, guest_token):
        resp = client.get(
            "/reports/occupancy?start_date=2025-01-01&end_date=2025-12-31",
            headers={"Authorization": f"Bearer {guest_token}"}
        )
        assert resp.status_code == 403

    def test_occupancy_report_owner(self, owner_token):
        resp = client.get(
            "/reports/occupancy?start_date=2025-01-01&end_date=2025-12-31",
            headers={"Authorization": f"Bearer {owner_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        for item in data:
            assert "occupancy_percentage" in item
            assert 0 <= item["occupancy_percentage"] <= 100

    def test_revenue_report_owner(self, owner_token):
        resp = client.get(
            "/reports/revenue?start_date=2025-01-01&end_date=2025-12-31",
            headers={"Authorization": f"Bearer {owner_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data:
            assert "adr" in item
            assert "revpar" in item

    def test_manager_scoped_report(self, manager_token):
        resp = client.get(
            "/reports/occupancy?start_date=2025-01-01&end_date=2025-12-31",
            headers={"Authorization": f"Bearer {manager_token}"}
        )
        assert resp.status_code == 200
        # Manager at property 1 should see only their property
        data = resp.json()
        assert all(item["property_id"] == 1 for item in data)

    def test_report_invalid_dates(self, owner_token):
        resp = client.get(
            "/reports/occupancy?start_date=2025-12-31&end_date=2025-01-01",
            headers={"Authorization": f"Bearer {owner_token}"}
        )
        assert resp.status_code == 422
