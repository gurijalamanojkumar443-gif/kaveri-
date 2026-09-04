"""
State definitions for Kaveri AI Agent.
Manages conversational memory, tool executions, and confirmation guardrails.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    tool_call_id: str
    name: str
    result: Any
    success: bool = True
    error: Optional[str] = None


class PendingAction(BaseModel):
    action_type: str  # e.g., "cancel_booking"
    booking_id: Optional[int] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    prompt_message: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant" | "system" | "tool"
    content: str
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AgentState(BaseModel):
    session_id: str
    guest_id: Optional[int] = None
    guest_name: Optional[str] = "Valued Guest"
    guest_email: Optional[str] = None
    messages: List[ChatMessage] = Field(default_factory=list)
    pending_action: Optional[PendingAction] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def add_message(self, role: str, content: str, tool_calls: Optional[List[ToolCall]] = None, tool_call_id: Optional[str] = None) -> ChatMessage:
        msg = ChatMessage(
            role=role,
            content=content,
            tool_calls=tool_calls,
            tool_call_id=tool_call_id
        )
        self.messages.append(msg)
        return msg

    def clear_pending_action(self):
        self.pending_action = None
