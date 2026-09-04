"""
tests/test_agent.py — Comprehensive tests for Kaveri AI Agent.
Tests tool listing, conversational intents, database queries, guest scoping,
spending calculations, room search, and multi-turn human confirmation cancellation flow.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
PASSWORD = "Password123!"


@pytest.fixture(scope="module")
def guest_token():
    resp = client.post("/auth/login", json={"email": "aarav.sharma@example.com", "password": PASSWORD})
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def guest_headers(guest_token):
    return {"Authorization": f"Bearer {guest_token}"}


class TestKaveriAIAgentAPI:
    def test_list_agent_tools(self):
        resp = client.get("/agent/tools")
        assert resp.status_code == 200
        tools = resp.json()
        assert isinstance(tools, list)
        tool_names = [t["name"] for t in tools]
        assert "get_my_bookings" in tool_names
        assert "get_pending_bookings" in tool_names
        assert "calculate_total_spending" in tool_names
        assert "search_available_rooms" in tool_names
        assert "initiate_cancellation" in tool_names
        assert "confirm_cancellation" in tool_names

    def test_get_prompt_suggestions(self):
        resp = client.get("/agent/suggestions")
        assert resp.status_code == 200
        suggestions = resp.json()
        assert len(suggestions) >= 4
        assert any("bookings" in s["label"].lower() for s in suggestions)

    def test_agent_chat_greeting(self, guest_headers):
        resp = client.post(
            "/agent/chat",
            json={"message": "Hello, good morning!"},
            headers=guest_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "Namaste" in data["reply"] or "welcome" in data["reply"].lower()
        assert "session_id" in data
        assert data["guest_name"] != ""

    def test_agent_get_my_bookings_tool(self, guest_headers):
        resp = client.post(
            "/agent/chat",
            json={"message": "Show my bookings"},
            headers=guest_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["tool_traces"]) >= 1
        assert data["tool_traces"][0]["tool_name"] == "get_my_bookings"
        assert "Kaveri" in data["reply"] or "Itinerary" in data["reply"] or "booking" in data["reply"].lower()

    def test_agent_get_pending_bookings_tool(self, guest_headers):
        resp = client.post(
            "/agent/chat",
            json={"message": "What bookings are still pending or unpaid?"},
            headers=guest_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["tool_traces"]) >= 1
        assert data["tool_traces"][0]["tool_name"] == "get_pending_bookings"
        assert "pending" in data["reply"].lower() or "caught up" in data["reply"].lower()

    def test_agent_calculate_spending_tool(self, guest_headers):
        resp = client.post(
            "/agent/chat",
            json={"message": "How much have I spent on hotel bookings?"},
            headers=guest_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["tool_traces"]) >= 1
        assert data["tool_traces"][0]["tool_name"] == "calculate_total_spending"
        assert "₹" in data["reply"]
        assert "Spending Summary" in data["reply"]

    def test_agent_search_available_rooms_tool(self, guest_headers):
        resp = client.post(
            "/agent/chat",
            json={"message": "Find me a Deluxe room in Coorg for 2 guests"},
            headers=guest_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["tool_traces"]) >= 1
        assert data["tool_traces"][0]["tool_name"] == "search_available_rooms"
        assert "Available" in data["reply"] or "Coorg" in data["reply"] or "Room" in data["reply"]

    def test_agent_resort_info_tool(self, guest_headers):
        resp = client.post(
            "/agent/chat",
            json={"message": "Tell me about the Ooty resort amenities and location"},
            headers=guest_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["tool_traces"]) >= 1
        assert data["tool_traces"][0]["tool_name"] == "get_resort_info"
        assert "Ooty" in data["reply"] or "Kaveri" in data["reply"]

    def test_agent_cancellation_confirmation_guardrail(self, guest_headers):
        # Step 1: Request cancellation
        sess_id = "test-agent-cancel-flow-1"
        resp = client.post(
            "/agent/chat",
            json={"message": "Cancel my booking", "session_id": sess_id},
            headers=guest_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["tool_traces"]) >= 1
        assert data["tool_traces"][0]["tool_name"] == "initiate_cancellation"
        assert data["pending_action"] is not None
        assert data["pending_action"]["action_type"] == "cancel_booking"
        assert "Would you like me to proceed" in data["reply"] or "Verification" in data["reply"]

        # Step 2: Negative confirmation (abort)
        resp_decline = client.post(
            "/agent/chat",
            json={"message": "No, keep my booking active", "session_id": sess_id},
            headers=guest_headers
        )
        assert resp_decline.status_code == 200
        decline_data = resp_decline.json()
        assert decline_data["pending_action"] is None
        assert "kept your reservation" in decline_data["reply"].lower() or "active" in decline_data["reply"].lower()

    def test_agent_reset_session(self, guest_headers):
        sess_id = "test-reset-session"
        resp = client.post(f"/agent/reset?session_id={sess_id}", headers=guest_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
