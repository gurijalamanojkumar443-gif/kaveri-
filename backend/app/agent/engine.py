"""
Core reasoning and execution engine for Kaveri AI Agent.
Coordinates multi-turn memory, human confirmation guardrails, and tool dispatching.
"""

import os
import re
import uuid
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.agent.state import AgentState, ChatMessage, ToolCall, ToolResult, PendingAction
from app.agent.prompts import KAVERI_CONCIERGE_SYSTEM_PROMPT
from app.agent import tools as agent_tools


class KaveriAgentEngine:
    """
    Intelligent Agent Engine for Kaveri Stays.
    Combines LLM tool-calling capabilities with deterministic safety guardrails.
    """

    def __init__(self):
        self._sessions: Dict[str, AgentState] = {}

    def get_or_create_state(
        self,
        session_id: Optional[str] = None,
        guest_id: Optional[int] = None,
        guest_name: Optional[str] = None,
        guest_email: Optional[str] = None
    ) -> AgentState:
        """Retrieve existing conversational state or create a fresh session."""
        if not session_id or session_id not in self._sessions:
            sess_id = session_id or str(uuid.uuid4())
            state = AgentState(
                session_id=sess_id,
                guest_id=guest_id,
                guest_name=guest_name or "Valued Guest",
                guest_email=guest_email,
                messages=[]
            )
            self._sessions[sess_id] = state
            return state

        state = self._sessions[session_id]
        if guest_id:
            state.guest_id = guest_id
        if guest_name:
            state.guest_name = guest_name
        if guest_email:
            state.guest_email = guest_email
        return state

    def clear_session(self, session_id: str):
        """Reset or clear session state."""
        if session_id in self._sessions:
            del self._sessions[session_id]

    def execute_tool(
        self,
        db: Session,
        tool_name: str,
        arguments: Dict[str, Any],
        guest_id: Optional[int] = None
    ) -> ToolResult:
        """
        Executes a registered tool against PostgreSQL with guest isolation.
        """
        tool_id = f"call_{uuid.uuid4().hex[:8]}"
        try:
            if tool_name == "get_my_bookings":
                if not guest_id:
                    return ToolResult(tool_call_id=tool_id, name=tool_name, result=[], success=True)
                res = agent_tools.get_my_bookings(
                    db=db,
                    guest_id=guest_id,
                    status=arguments.get("status")
                )
                return ToolResult(tool_call_id=tool_id, name=tool_name, result=res, success=True)

            elif tool_name == "get_pending_bookings":
                if not guest_id:
                    return ToolResult(tool_call_id=tool_id, name=tool_name, result=[], success=True)
                res = agent_tools.get_pending_bookings(db=db, guest_id=guest_id)
                return ToolResult(tool_call_id=tool_id, name=tool_name, result=res, success=True)

            elif tool_name == "calculate_total_spending":
                if not guest_id:
                    return ToolResult(
                        tool_call_id=tool_id,
                        name=tool_name,
                        result={"total_bookings": 0, "total_cost": 0.0, "total_paid": 0.0, "total_balance_due": 0.0, "property_breakdown": {}},
                        success=True
                    )
                res = agent_tools.calculate_total_spending(
                    db=db,
                    guest_id=guest_id,
                    year=arguments.get("year"),
                    property_name=arguments.get("property_name")
                )
                return ToolResult(tool_call_id=tool_id, name=tool_name, result=res, success=True)

            elif tool_name == "search_available_rooms":
                res = agent_tools.search_available_rooms(
                    db=db,
                    property_name_or_city=arguments.get("property_name_or_city"),
                    check_in=arguments.get("check_in"),
                    check_out=arguments.get("check_out"),
                    guests=arguments.get("guests", 1)
                )
                return ToolResult(tool_call_id=tool_id, name=tool_name, result=res, success=True)

            elif tool_name == "get_resort_info":
                res = agent_tools.get_resort_info(
                    db=db,
                    property_name_or_city=arguments.get("property_name_or_city")
                )
                return ToolResult(tool_call_id=tool_id, name=tool_name, result=res, success=True)

            elif tool_name == "initiate_cancellation":
                if not guest_id:
                    return ToolResult(tool_call_id=tool_id, name=tool_name, result={"success": False, "error": "Please log in to cancel reservations."}, success=False)
                res = agent_tools.initiate_cancellation(
                    db=db,
                    guest_id=guest_id,
                    booking_id=arguments.get("booking_id"),
                    search_term=arguments.get("search_term")
                )
                return ToolResult(tool_call_id=tool_id, name=tool_name, result=res, success=res.get("success", False))

            elif tool_name == "confirm_cancellation":
                if not guest_id:
                    return ToolResult(tool_call_id=tool_id, name=tool_name, result={"success": False, "error": "Authentication required."}, success=False)
                res = agent_tools.confirm_cancellation(
                    db=db,
                    guest_id=guest_id,
                    booking_id=arguments["booking_id"]
                )
                return ToolResult(tool_call_id=tool_id, name=tool_name, result=res, success=res.get("success", False))

            elif tool_name == "initiate_booking":
                res = agent_tools.initiate_booking(
                    db=db,
                    guest_id=guest_id,
                    room_number=arguments.get("room_number"),
                    property_name_or_city=arguments.get("property_name_or_city"),
                    room_type=arguments.get("room_type"),
                    check_in=arguments.get("check_in"),
                    check_out=arguments.get("check_out"),
                    guest_count=arguments.get("guest_count", 1)
                )
                return ToolResult(tool_call_id=tool_id, name=tool_name, result=res, success=res.get("success", False))

            elif tool_name == "confirm_booking":
                if not guest_id:
                    return ToolResult(tool_call_id=tool_id, name=tool_name, result={"success": False, "error": "Please log in to complete booking."}, success=False)
                res = agent_tools.confirm_booking(
                    db=db,
                    guest_id=guest_id,
                    room_id=arguments["room_id"],
                    check_in=arguments["check_in"],
                    check_out=arguments["check_out"],
                    guest_count=arguments.get("guest_count", 1),
                    payment_method=arguments.get("payment_method", "upi")
                )
                return ToolResult(tool_call_id=tool_id, name=tool_name, result=res, success=res.get("success", False))

            else:
                return ToolResult(
                    tool_call_id=tool_id,
                    name=tool_name,
                    result=None,
                    success=False,
                    error=f"Unknown tool: {tool_name}"
                )

        except Exception as e:
            return ToolResult(
                tool_call_id=tool_id,
                name=tool_name,
                result=None,
                success=False,
                error=str(e)
            )

    def process_message(
        self,
        db: Session,
        user_message: str,
        state: AgentState
    ) -> Tuple[str, List[ToolResult], Optional[PendingAction]]:
        """
        Main cognitive loop:
        1. Checks for active pending confirmations (Cancellation or Booking approval)
        2. Reasons about intent and chooses tool(s)
        3. Executes tool(s) with PostgreSQL data
        4. Synthesizes response and updates conversational memory
        """
        raw_msg = user_message.strip()
        lower_msg = raw_msg.lower()
        guest_id = state.guest_id
        executed_tools: List[ToolResult] = []

        # Record user message in history
        state.add_message(role="user", content=raw_msg)

        # ─── 1. CHECK HUMAN CONFIRMATION GUARDRAIL ───────────────────────────
        if state.pending_action:
            pending = state.pending_action

            # Identify affirmation vs negation
            is_yes_start = lower_msg.startswith("yes") or lower_msg.startswith("yep") or lower_msg.startswith("sure") or lower_msg.startswith("ok")
            is_no_start = lower_msg.startswith("no") or lower_msg.startswith("nope") or lower_msg.startswith("don't") or lower_msg.startswith("stop")

            affirmative_words = ["yes", "confirm", "proceed", "cancel it", "cancel booking", "book it", "reserve it", "sure", "ok", "yep", "do it", "confirm booking", "confirm reservation", "pay deposit"]
            negative_words = ["no", "cancel that", "don't", "keep it", "nevermind", "abort", "wait", "nope", "stop", "change", "cancel request", "keep booking"]

            is_affirmative = is_yes_start or any(w in lower_msg for w in affirmative_words)
            is_negative = is_no_start or any(w in lower_msg for w in negative_words)

            if is_yes_start:
                is_negative = False
            elif is_no_start:
                is_affirmative = False

            if pending.action_type == "cancel_booking":
                if is_affirmative and not is_negative:
                    booking_id = pending.booking_id
                    tool_res = self.execute_tool(
                        db=db,
                        tool_name="confirm_cancellation",
                        arguments={"booking_id": booking_id},
                        guest_id=guest_id
                    )
                    executed_tools.append(tool_res)
                    state.clear_pending_action()

                    reply = (
                        f"✦ **Cancellation Confirmed**\n\n"
                        f"Booking **#{booking_id}** has been cancelled as requested. "
                        f"A confirmation notice has been noted on your profile and any eligible refund is being processed.\n\n"
                        f"Is there anything else I can assist you with today, {state.guest_name}?"
                    )
                    state.add_message(role="assistant", content=reply)
                    return reply, executed_tools, None

                elif is_negative:
                    booking_id = pending.booking_id
                    state.clear_pending_action()
                    reply = (
                        f"Understood! I have kept your reservation for Booking **#{booking_id}** active and untouched. "
                        f"Let me know if you would like to explore room upgrades, amenities, or other dates instead!"
                    )
                    state.add_message(role="assistant", content=reply)
                    return reply, executed_tools, None

            elif pending.action_type == "confirm_booking":
                if is_affirmative and not is_negative:
                    d = pending.details
                    tool_res = self.execute_tool(
                        db=db,
                        tool_name="confirm_booking",
                        arguments={
                            "room_id": d["room_id"],
                            "check_in": d["check_in"],
                            "check_out": d["check_out"],
                            "guest_count": d.get("guest_count", 1),
                            "payment_method": "upi"
                        },
                        guest_id=guest_id
                    )
                    executed_tools.append(tool_res)
                    state.clear_pending_action()

                    if tool_res.success:
                        res_data = tool_res.result
                        reply = (
                            f"🎉 **Reservation Confirmed!** ✦\n\n"
                            f"Your luxury stay has been reserved successfully:\n"
                            f"• **Booking ID**: `#{res_data['booking_id']}`\n"
                            f"• **Resort**: **{res_data['property_name']}** ({res_data['city']})\n"
                            f"• **Room**: {res_data['room_type']} (Room #{res_data['room_number']})\n"
                            f"• **Dates**: {res_data['check_in']} → {res_data['check_out']} ({res_data['nights']} night{'s' if res_data['nights'] != 1 else ''})\n"
                            f"• **Total Cost**: ₹{res_data['total_cost']:,.2f} | **Deposit Recorded**: ₹{res_data['total_paid']:,.2f}\n"
                            f"• **Balance Due at Check-in**: ₹{res_data['balance_due']:,.2f}\n\n"
                            f"We have registered this booking under your account, {state.guest_name}. You can manage or make additional payments anytime from your dashboard!"
                        )
                    else:
                        err_msg = tool_res.result.get("error", "Unable to complete reservation.")
                        reply = f"Sorry, could not finalize reservation: {err_msg}\n\nPlease try alternate dates or another suite."
                    state.add_message(role="assistant", content=reply)
                    return reply, executed_tools, None

                elif is_negative:
                    state.clear_pending_action()
                    reply = (
                        f"No problem at all! I have cancelled this reservation request. "
                        f"Feel free to ask me for other dates, room types, or amenities whenever you are ready!"
                    )
                    state.add_message(role="assistant", content=reply)
                    return reply, executed_tools, None

        # ─── 2. REASONING & INTENT ROUTING ───────────────────────────────────

        # Check authentication requirement for user-specific actions
        is_personal_query = any(w in lower_msg for w in ["my booking", "my stay", "show my", "spent", "spending", "total money", "pending booking", "unpaid booking", "my balance", "cancel my", "cancel booking"])

        if is_personal_query and not guest_id:
            reply = (
                f"Namaste! You are currently browsing as a guest visitor. ✦\n\n"
                f"To access your personal itinerary, pending balances, and spending history, "
                f"please **Log In** or **Register** using the account button above.\n\n"
                f"In the meantime, I can still help you search room availability, check rates, and explore resort amenities across Coorg, Ooty, and Alleppey!"
            )
            state.add_message(role="assistant", content=reply)
            return reply, executed_tools, None

        # 2a. Direct Room Booking Intent (e.g. "book 205 room", "book room 205", "reserve room 302")
        is_book_keyword = any(w in lower_msg for w in ["book", "reserve", "reservation for", "book room", "book a stay", "reserve room"])
        is_not_view_or_cancel = not any(w in lower_msg for w in ["cancel", "pending", "spent", "spending", "show my", "my booking", "what are", "amenit", "review"])

        if is_book_keyword and is_not_view_or_cancel:
            # Extract room number (e.g. 205, 301, 302, 101)
            match_num = re.search(r'(?:room\s*#?|#\s*)(\d{2,4})', lower_msg) or re.search(r'\b(\d{3})\b', lower_msg)
            room_num_str = match_num.group(1) if match_num else None

            prop_val = None
            if "coorg" in lower_msg or "riverside" in lower_msg:
                prop_val = "Coorg"
            elif "ooty" in lower_msg or "hilltop" in lower_msg:
                prop_val = "Ooty"
            elif "alleppey" in lower_msg or "backwater" in lower_msg:
                prop_val = "Alleppey"

            # Parse guests count
            guest_match = re.search(r'(\d+)\s*(guest|person|people)', lower_msg)
            guests_num = int(guest_match.group(1)) if guest_match else 1

            if not guest_id:
                # User not logged in, prompt login
                tool_res = self.execute_tool(
                    db=db,
                    tool_name="initiate_booking",
                    arguments={"room_number": room_num_str, "property_name_or_city": prop_val, "guest_count": guests_num},
                    guest_id=None
                )
                executed_tools.append(tool_res)
                if tool_res.success:
                    info = tool_res.result
                    reply = (
                        f"🏨 I found **{info['room_type']} Suite (Room #{info['room_number']})** at **{info['property_name']}** ({info['city']})!\n"
                        f"📅 {info['check_in']} → {info['check_out']} ({info['nights']} nights)\n"
                        f"🌙 Rate: ₹{info['nightly_rate']:,.2f}/night · Total: **₹{info['total_cost']:,.2f}**\n\n"
                        f"✦ Please **Log In** or **Register** to confirm and finalize this booking under your account."
                    )
                else:
                    reply = f"I could not locate Room #{room_num_str or 'requested'} for booking. Please try another room number or let me search available rooms for you."
                state.add_message(role="assistant", content=reply)
                return reply, executed_tools, None

            # Guest is logged in -> initiate booking with confirmation prompt
            tool_res = self.execute_tool(
                db=db,
                tool_name="initiate_booking",
                arguments={"room_number": room_num_str, "property_name_or_city": prop_val, "guest_count": guests_num},
                guest_id=guest_id
            )
            executed_tools.append(tool_res)

            if tool_res.success:
                info = tool_res.result
                state.pending_action = PendingAction(
                    action_type="confirm_booking",
                    booking_id=None,
                    details=info,
                    prompt_message=info["confirmation_prompt"]
                )
                reply = (
                    f"🏨 **Reservation Summary for Room #{info['room_number']}**\n\n"
                    f"• **Resort**: {info['property_name']} ({info['city']})\n"
                    f"• **Suite**: {info['room_type']} Suite (Max {info['max_occupancy']} guests)\n"
                    f"• **Dates**: {info['check_in']} → {info['check_out']} ({info['nights']} night{'s' if info['nights'] != 1 else ''})\n"
                    f"• **Nightly Rate**: ₹{info['nightly_rate']:,.2f}\n"
                    f"• **Total Cost**: **₹{info['total_cost']:,.2f}**\n"
                    f"• **Initial Deposit (20%)**: ₹{info['deposit_amount']:,.2f}\n\n"
                    f"**Would you like me to confirm and reserve Room #{info['room_number']} now for your stay?**\n"
                    f"*(Reply 'Yes' to confirm or 'No' to cancel)*"
                )
                state.add_message(role="assistant", content=reply)
                return reply, executed_tools, state.pending_action
            else:
                err_text = tool_res.result.get("error", "Room is not available.")
                reply = f"{err_text}\n\nWould you like me to search other available suites in Coorg, Ooty, or Alleppey for you?"
                state.add_message(role="assistant", content=reply)
                return reply, executed_tools, None

        # 2b. Cancellation intent
        if any(w in lower_msg for w in ["cancel", "cancellation", "delete booking"]):
            match_id = re.search(r'#?(\d+)', lower_msg)
            booking_id = int(match_id.group(1)) if match_id else None

            tool_res = self.execute_tool(
                db=db,
                tool_name="initiate_cancellation",
                arguments={"booking_id": booking_id, "search_term": raw_msg},
                guest_id=guest_id
            )
            executed_tools.append(tool_res)

            if tool_res.success and tool_res.result.get("requires_confirmation"):
                info = tool_res.result
                state.pending_action = PendingAction(
                    action_type="cancel_booking",
                    booking_id=info["booking_id"],
                    details=info,
                    prompt_message=info["confirmation_prompt"]
                )
                reply = (
                    f"⚠️ **Cancellation Verification**\n\n"
                    f"I located your reservation:\n"
                    f"• **Booking ID**: #{info['booking_id']}\n"
                    f"• **Resort**: {info['property_name']} ({info['city']})\n"
                    f"• **Dates**: {info['check_in']} → {info['check_out']}\n"
                    f"• **Room Type**: {info['room_type']}\n"
                    f"• **Paid Amount**: ₹{info['total_paid']:,.2f}\n"
                    f"• **Refund Status**: ₹{info['estimated_refund']:,.2f} ({info['policy_note']})\n\n"
                    f"**Would you like me to proceed with cancelling Booking #{info['booking_id']}?** "
                    f"*(Reply 'Yes' to confirm or 'No' to keep your stay)*"
                )
                state.add_message(role="assistant", content=reply)
                return reply, executed_tools, state.pending_action
            else:
                err = tool_res.result.get("error", "Could not locate an active booking to cancel.")
                reply = f"I was unable to initiate cancellation: {err}\n\nYou can view all your active stays by asking *'Show my bookings'*."
                state.add_message(role="assistant", content=reply)
                return reply, executed_tools, None

        # 2c. Pending bookings intent
        if any(w in lower_msg for w in ["pending", "unpaid", "due", "balance"]):
            tool_res = self.execute_tool(
                db=db,
                tool_name="get_pending_bookings",
                arguments={},
                guest_id=guest_id
            )
            executed_tools.append(tool_res)
            pending_items = tool_res.result or []

            if not pending_items:
                reply = (
                    f"✨ **All Caught Up!**\n\n"
                    f"You have no pending or unpaid bookings. All your current reservations are fully confirmed and up to date!\n\n"
                    f"Would you like to explore available rooms for your next luxury getaway?"
                )
            else:
                lines = [f"Found **{len(pending_items)} pending / action-required booking(s)** for your account:\n"]
                for b in pending_items:
                    lines.append(
                        f"• **Booking #{b['booking_id']}** at **{b['property_name']}** ({b['city']})\n"
                        f"  📅 {b['check_in']} to {b['check_out']} ({b['nights']} nights)\n"
                        f"  🏨 {b['room_type']} (Room {b['room_number']})\n"
                        f"  💳 Total: ₹{b['total_cost']:,.2f} | Paid: ₹{b['total_paid']:,.2f} | **Balance Due: ₹{b['balance_due']:,.2f}**\n"
                        f"  🏷️ Status: `{b['status']}` ({b['payment_status']})\n"
                    )
                lines.append("\nYou can complete payment from your Bookings dashboard or let me know if you would like to modify or cancel any stay.")
                reply = "\n".join(lines)

            state.add_message(role="assistant", content=reply)
            return reply, executed_tools, None

        # 2d. Spending / Expense calculation intent
        if any(w in lower_msg for w in ["spent", "spending", "cost", "total money", "expense", "how much have i", "how much did i", "finance"]):
            match_yr = re.search(r'\b(202[0-9])\b', lower_msg)
            year_val = int(match_yr.group(1)) if match_yr else None

            prop_val = None
            if "coorg" in lower_msg:
                prop_val = "Coorg"
            elif "ooty" in lower_msg:
                prop_val = "Ooty"
            elif "alleppey" in lower_msg:
                prop_val = "Alleppey"

            tool_res = self.execute_tool(
                db=db,
                tool_name="calculate_total_spending",
                arguments={"year": year_val, "property_name": prop_val},
                guest_id=guest_id
            )
            executed_tools.append(tool_res)
            data = tool_res.result or {}

            if data.get("total_bookings", 0) == 0:
                reply = (
                    f"💳 **Spending Summary**\n\n"
                    f"You have no recorded stays or payments on this account yet (Total: **₹0.00**).\n\n"
                    f"Would you like me to help you find and reserve a luxury suite in Coorg, Ooty, or Alleppey?"
                )
                state.add_message(role="assistant", content=reply)
                return reply, executed_tools, None

            scope_str = f" in {year_val}" if year_val else ""
            if prop_val:
                scope_str += f" at Kaveri {prop_val}"

            breakdown_lines = []
            for p_name, b_info in data.get("property_breakdown", {}).items():
                breakdown_lines.append(
                    f"  • **{p_name}**: ₹{b_info['total_paid']:,.2f} across {b_info['bookings_count']} stay(s)"
                )
            breakdown_text = "\n".join(breakdown_lines) if breakdown_lines else "  *(No specific resort breakdown)*"

            reply = (
                f"💳 **Spending Summary{scope_str}**\n\n"
                f"• **Total Stays Recorded**: {data['total_bookings']}\n"
                f"• **Total Amount Paid**: **₹{data['total_paid']:,.2f}**\n"
                f"• **Total Value of Bookings**: ₹{data['total_cost']:,.2f}\n"
                f"• **Remaining Balance Due**: ₹{data['total_balance_due']:,.2f}\n\n"
                f"**Property Breakdown**:\n{breakdown_text}\n\n"
                f"Let me know if you would like an invoice breakdown for any specific stay!"
            )
            state.add_message(role="assistant", content=reply)
            return reply, executed_tools, None

        # 2e. Room Search / Availability intent
        if any(w in lower_msg for w in ["find", "search", "available", "availability", "vacanc", "room", "rates"]):
            prop_val = None
            if "coorg" in lower_msg or "riverside" in lower_msg:
                prop_val = "Coorg"
            elif "ooty" in lower_msg or "hilltop" in lower_msg:
                prop_val = "Ooty"
            elif "alleppey" in lower_msg or "backwater" in lower_msg:
                prop_val = "Alleppey"

            guest_match = re.search(r'(\d+)\s*(guest|person|people)', lower_msg)
            guests_num = int(guest_match.group(1)) if guest_match else 1

            tool_res = self.execute_tool(
                db=db,
                tool_name="search_available_rooms",
                arguments={"property_name_or_city": prop_val, "guests": guests_num},
                guest_id=guest_id
            )
            executed_tools.append(tool_res)
            rooms = tool_res.result or []

            if not rooms:
                reply = (
                    f"I searched our sanctuaries but could not find available rooms matching those exact criteria. "
                    f"Would you like to try alternate dates or check another property?"
                )
            else:
                top_rooms = rooms[:5]
                lines = [f"🏨 **Available Sanctuary Rooms** ({len(rooms)} option{'s' if len(rooms) != 1 else ''} found):\n"]
                for r in top_rooms:
                    lines.append(
                        f"• **{r['room_type']} Suite** (Room #{r['room_number']}) — **{r['property_name']}** ({r['city']})\n"
                        f"  🌙 Rate: **₹{r['nightly_rate']:,.2f} / night** (Total: ₹{r['total_rate']:,.2f} for {r['nights']} nights)\n"
                        f"  👥 Max Occupancy: {r['max_occupancy']} guests | Dates: {r['check_in']} → {r['check_out']}\n"
                    )
                lines.append("To reserve any suite, simply tell me (e.g. *'Book Room 205'* or *'Book Deluxe in Ooty'*)!")
                reply = "\n".join(lines)

            state.add_message(role="assistant", content=reply)
            return reply, executed_tools, None

        # 2f. My Bookings intent
        if any(w in lower_msg for w in ["my booking", "bookings", "my stay", "reservations", "show my"]):
            status_filter = None
            if "confirmed" in lower_msg:
                status_filter = "confirmed"
            elif "cancel" in lower_msg:
                status_filter = "cancelled"
            elif "past" in lower_msg or "completed" in lower_msg or "checkout" in lower_msg:
                status_filter = "checked_out"

            tool_res = self.execute_tool(
                db=db,
                tool_name="get_my_bookings",
                arguments={"status": status_filter},
                guest_id=guest_id
            )
            executed_tools.append(tool_res)
            bookings = tool_res.result or []

            if not bookings:
                reply = (
                    f"You do not have any {status_filter or 'active'} bookings on record at the moment. "
                    f"Would you like me to find available suites in Coorg, Ooty, or Alleppey for you?"
                )
            else:
                lines = [f"📋 **Your Kaveri Stays Itinerary** ({len(bookings)} reservation{'s' if len(bookings) != 1 else ''}):\n"]
                for b in bookings:
                    status_icon = "🟢" if b["status"] == "confirmed" else ("🔵" if b["status"] == "checked_in" else ("⚪" if b["status"] == "checked_out" else "🔴"))
                    lines.append(
                        f"{status_icon} **Booking #{b['booking_id']}** · **{b['property_name']}** ({b['city']})\n"
                        f"  📅 {b['check_in']} → {b['check_out']} ({b['nights']} nights, {b['guest_count']} guests)\n"
                        f"  🏨 {b['room_type']} Suite (Room {b['room_number']})\n"
                        f"  💳 Total: ₹{b['total_cost']:,.2f} | Status: `{b['status']}` ({b['payment_status']})\n"
                    )
                lines.append("Let me know if you would like details on cancellation policy, room amenities, or payment receipts!")
                reply = "\n".join(lines)

            state.add_message(role="assistant", content=reply)
            return reply, executed_tools, None

        # 2g. Property / Resort Info intent
        if any(w in lower_msg for w in ["property", "resort", "hotel", "amenit", "coorg", "ooty", "alleppey", "location", "rating", "review"]):
            prop_val = None
            if "coorg" in lower_msg or "riverside" in lower_msg:
                prop_val = "Coorg"
            elif "ooty" in lower_msg or "hilltop" in lower_msg:
                prop_val = "Ooty"
            elif "alleppey" in lower_msg or "backwater" in lower_msg:
                prop_val = "Alleppey"

            tool_res = self.execute_tool(
                db=db,
                tool_name="get_resort_info",
                arguments={"property_name_or_city": prop_val},
                guest_id=guest_id
            )
            executed_tools.append(tool_res)
            props = tool_res.result or []

            lines = ["✦ **Kaveri Stays Sanctuary Overview**:\n"]
            for p in props:
                amenities_str = " · ".join(p["amenities"][:4])
                lines.append(
                    f"🏛️ **{p['name']}** ({p['stars']}★ Luxury Sanctuary)\n"
                    f"  📍 *{p['location']}* · ⭐ **{p['average_rating']}/5.0** ({p['review_count']} verified reviews)\n"
                    f"  🌿 *\"{p['tagline']}\"*\n"
                    f"  ✨ Features: {amenities_str}\n"
                )
            lines.append("Feel free to ask me for room rates or live availability for any of our sanctuaries!")
            reply = "\n".join(lines)

            state.add_message(role="assistant", content=reply)
            return reply, executed_tools, None

        # 2h. Greeting & Fallback
        if any(w in lower_msg for w in ["hello", "hi", "hey", "namaste", "good morning", "good evening"]):
            reply = (
                f"Namaste and welcome, {state.guest_name}! ✦\n\n"
                f"I am your **Kaveri AI Concierge**. I can assist you with:\n"
                f"• 🏨 **Instant Room Reservations** (e.g. *'Book Room 205'*)\n"
                f"• 📋 **Checking your bookings & pending balances**\n"
                f"• 💳 **Calculating your personal spending & receipts**\n"
                f"• 🌲 **Finding live room availability in Coorg, Ooty & Alleppey**\n"
                f"• ⚠️ **Safe booking cancellations with refund checks**\n"
                f"• ⭐ **Resort highlights, amenities & dining experiences**\n\n"
                f"How may I make your stay exceptional today?"
            )
            state.add_message(role="assistant", content=reply)
            return reply, executed_tools, None

        # General helpful fallback
        reply = (
            f"I would be delighted to help with that, {state.guest_name}! "
            f"As your Kaveri Stays AI Concierge, you can ask me to:\n\n"
            f"• *'Book Room 205'*\n"
            f"• *'Show my pending bookings'*\n"
            f"• *'How much have I spent on hotel bookings?'*\n"
            f"• *'Find a Deluxe room in Coorg for next weekend'*\n"
            f"• *'Cancel my upcoming booking'*\n"
            f"• *'Tell me about the Ooty resort amenities'*\n\n"
            f"What would you like to explore?"
        )
        state.add_message(role="assistant", content=reply)
        return reply, executed_tools, None


# Global singleton engine instance
_agent_engine_instance = KaveriAgentEngine()

def get_agent_engine() -> KaveriAgentEngine:
    return _agent_engine_instance
