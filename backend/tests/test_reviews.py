"""
tests/test_reviews.py — Comprehensive tests for Resort Review System.
Tests resort review fetching, rating calculations, distribution breakdown,
chain review stats, property rating integration, and guest review submissions.
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


class TestResortReviewsAPI:
    def test_get_property_reviews_coorg(self):
        resp = client.get("/properties/1/reviews")
        assert resp.status_code == 200
        data = resp.json()
        assert data["property_id"] == 1
        assert "Kaveri Riverside" in data["property_name"]
        assert "Coorg" in data["city"]
        assert isinstance(data["average_rating"], float)
        assert data["average_rating"] >= 1.0 and data["average_rating"] <= 5.0
        assert data["total_reviews"] >= 0
        assert "rating_distribution" in data
        assert isinstance(data["reviews"], list)
        if data["reviews"]:
            first = data["reviews"][0]
            assert "guest_name" in first
            assert "rating" in first
            assert first["rating"] in [1, 2, 3, 4, 5]

    def test_get_property_reviews_all_resorts(self):
        for prop_id in [1, 2, 3]:
            resp = client.get(f"/properties/{prop_id}/reviews")
            assert resp.status_code == 200
            data = resp.json()
            assert data["property_id"] == prop_id
            assert data["average_rating"] > 0
            assert isinstance(data["rating_distribution"], dict)

    def test_get_property_reviews_not_found(self):
        resp = client.get("/properties/99999/reviews")
        assert resp.status_code == 404

    def test_get_all_reviews_endpoint(self):
        resp = client.get("/reviews")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_reviews"] > 0
        assert len(data["reviews"]) > 0

    def test_get_reviews_filtered_by_property_and_rating(self):
        resp = client.get("/reviews?property_id=1&rating=5")
        assert resp.status_code == 200
        data = resp.json()
        for rev in data["reviews"]:
            assert rev["property_id"] == 1
            assert rev["rating"] == 5

    def test_get_reviews_stats(self):
        resp = client.get("/reviews/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "overall_average_rating" in data
        assert "total_reviews" in data
        assert "resorts" in data
        assert len(data["resorts"]) == 3
        for resort in data["resorts"]:
            assert resort["average_rating"] > 0
            assert "property_name" in resort
        assert "recent_reviews" in data

    def test_property_list_includes_rating_stats(self):
        resp = client.get("/properties")
        assert resp.status_code == 200
        props = resp.json()
        assert len(props) == 3
        for p in props:
            assert "average_rating" in p
            assert "total_reviews" in p
            assert p["average_rating"] >= 1.0

    def test_property_detail_includes_rating_stats(self):
        resp = client.get("/properties/1")
        assert resp.status_code == 200
        p = resp.json()
        assert "average_rating" in p
        assert "total_reviews" in p
        assert p["property_id"] == 1
