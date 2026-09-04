"""
FastAPI router for Kaveri AI Agent endpoints.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Account
from app.dependencies import get_current_user, get_optional_user
from app.schemas.agent import (
    ChatRequest,
    ChatResponse,
    ToolExecutionTrace,
    PendingActionDTO,
    AgentToolInfo
)
from app.agent.engine import get_agent_engine
from app.agent.prompts import AGENT_TOOL_DEFINITIONS

router = APIRouter(prefix="/agent", tags=["AI Agent"])


@router.post("/chat", response_model=ChatResponse, summary="Send natural language message to Kaveri AI Agent")
def agent_chat(
    req: ChatRequest,
    db: Session = Depends(get_db),
    current_user: Optional[Account] = Depends(get_optional_user)
):
    """
    Main conversational endpoint for Kaveri AI Concierge.
    Automatically scopes all booking queries and database operations to the authenticated user.
    """
    engine = get_agent_engine()

    # Determine guest identity from JWT token
    guest_id = current_user.guest_id if current_user and current_user.guest_id else (current_user.account_id if current_user else 1)
    guest_name = current_user.name if current_user else "Valued Guest"
    guest_email = current_user.email if current_user else None

    # Retrieve or initialize session state
    state = engine.get_or_create_state(
        session_id=req.session_id,
        guest_id=guest_id,
        guest_name=guest_name,
        guest_email=guest_email
    )

    # Process message through agent reasoning and tool execution loop
    reply_text, tool_results, pending_action = engine.process_message(
        db=db,
        user_message=req.message,
        state=state
    )

    # Map tool execution traces
    traces = [
        ToolExecutionTrace(
            tool_name=tr.name,
            arguments={},
            success=tr.success,
            result=tr.result,
            error=tr.error
        )
        for tr in tool_results
    ]

    # Map pending action if confirmation is required
    pending_dto = None
    if pending_action:
        pending_dto = PendingActionDTO(
            action_type=pending_action.action_type,
            booking_id=pending_action.booking_id,
            prompt_message=pending_action.prompt_message,
            details=pending_action.details
        )

    return ChatResponse(
        reply=reply_text,
        session_id=state.session_id,
        guest_name=state.guest_name,
        tool_traces=traces,
        pending_action=pending_dto,
        message_count=len(state.messages)
    )


@router.get("/tools", response_model=List[AgentToolInfo], summary="List available tools and capabilities")
def list_agent_tools():
    """Returns metadata about all registered database tools accessible to the agent."""
    tools_list = []
    for defn in AGENT_TOOL_DEFINITIONS:
        fn = defn["function"]
        tools_list.append(
            AgentToolInfo(
                name=fn["name"],
                description=fn["description"],
                parameters=fn.get("parameters", {})
            )
        )
    return tools_list


@router.post("/reset", summary="Reset conversation session memory")
def reset_session(
    session_id: str,
    current_user: Optional[Account] = Depends(get_optional_user)
):
    """Resets memory state for the given session ID."""
    engine = get_agent_engine()
    engine.clear_session(session_id)
    return {"status": "ok", "message": f"Session {session_id} memory cleared."}


@router.get("/suggestions", summary="Quick prompt suggestions for the chat interface")
def get_prompt_suggestions():
    """Returns rich starter prompt chips for the UI."""
    return [
        {"icon": "📋", "label": "Show my bookings", "prompt": "Show my bookings and itinerary."},
        {"icon": "⏳", "label": "Pending bookings", "prompt": "What bookings are still pending or unpaid?"},
        {"icon": "💳", "label": "Total spending", "prompt": "How much have I spent on hotel bookings?"},
        {"icon": "🌲", "label": "Coorg availability", "prompt": "Find me a Deluxe room in Coorg for next weekend."},
        {"icon": "🌊", "label": "Alleppey backwaters", "prompt": "Tell me about the Alleppey Backwater resort amenities."},
        {"icon": "⚠️", "label": "Cancel booking", "prompt": "I would like to cancel my upcoming booking."}
    ]
