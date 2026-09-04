"""
Pydantic schemas for Kaveri AI Agent endpoints.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="Natural language prompt for Kaveri AI Concierge")
    session_id: Optional[str] = Field(None, description="Optional conversation session ID for multi-turn memory")


class ToolExecutionTrace(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None


class PendingActionDTO(BaseModel):
    action_type: str
    booking_id: Optional[int] = None
    prompt_message: str
    details: Dict[str, Any] = Field(default_factory=dict)


class ChatMessageDTO(BaseModel):
    role: str
    content: str
    timestamp: str


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    guest_name: str
    tool_traces: List[ToolExecutionTrace] = Field(default_factory=list)
    pending_action: Optional[PendingActionDTO] = None
    message_count: int


class AgentToolInfo(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any]
