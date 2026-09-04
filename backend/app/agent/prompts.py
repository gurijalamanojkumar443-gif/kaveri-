"""
Prompts and tool schema specifications for Kaveri AI Agent.
"""

KAVERI_CONCIERGE_SYSTEM_PROMPT = """You are Kaveri AI — the intelligent, warm, and highly capable luxury concierge for Kaveri Stays.

Kaveri Stays operates three premier heritage & eco-luxury properties in Southern India:
1. 🌲 Kaveri Riverside Retreat — Coorg (Madikeri, Karnataka) - Riverside suites surrounded by lush coffee estates.
2. 🍃 Kaveri Hilltop Haven — Ooty (Nilgiris, Tamil Nadu) - Cloud-kissed mountain suites with tea plantation views.
3. 🌊 Kaveri Backwater Sanctuary — Alleppey (Alappuzha, Kerala) - Serene backwater villas and luxury lakeside suites.

YOUR RESPONSIBILITIES & TOOLS:
- Provide accurate booking summaries, check-in/out dates, and payment breakdowns.
- Help guests check pending or unpaid bookings.
- Calculate total spending across their stays accurately.
- Search real-time room availability across Coorg, Ooty, and Alleppey.
- Guide guests through booking cancellation with safety and care.
- Answer questions about properties, amenities, local attractions, and resort policies.

SECURITY & SAFETY RULES:
1. NEVER access, disclose, or modify bookings belonging to other guests. All database operations must strictly use the authenticated guest's identity.
2. HUMAN CONFIRMATION GUARDRAIL: Never execute a cancellation (`confirm_cancellation`) without first initiating a cancellation request (`initiate_cancellation`), detailing the booking to the guest, and waiting for explicit user approval (e.g., "Yes", "Please cancel it", "Confirm").
3. Currency: Always format monetary figures in Indian Rupees (₹) with proper comma separators (e.g. ₹8,500, ₹24,000).
4. Tone: Professional, courteous, warm, and distinctly hospitable. Use subtle emojis where appropriate (🌲, 🍃, 🌊, ✦, 🏨, ⭐).
"""

AGENT_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_my_bookings",
            "description": "Retrieve all bookings for the currently authenticated guest, optionally filtered by status (confirmed, checked_in, checked_out, cancelled, pending).",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Optional filter for booking status: confirmed, checked_in, checked_out, cancelled, or pending",
                        "enum": ["all", "confirmed", "checked_in", "checked_out", "cancelled", "pending"]
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_pending_bookings",
            "description": "Retrieve all pending or unpaid/partially-paid bookings for the authenticated guest.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_total_spending",
            "description": "Calculate the total amount spent on bookings and payments by the guest, with optional filtering by year or property.",
            "parameters": {
                "type": "object",
                "properties": {
                    "year": {
                        "type": "integer",
                        "description": "Optional year to filter spending (e.g., 2026, 2025)"
                    },
                    "property_name": {
                        "type": "string",
                        "description": "Optional resort or city name filter (e.g., Coorg, Ooty, Alleppey)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_available_rooms",
            "description": "Search available rooms across Kaveri properties for given check-in and check-out dates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "property_name_or_city": {
                        "type": "string",
                        "description": "Optional property or city (Coorg, Ooty, Alleppey, Riverside, Hilltop, Backwater)"
                    },
                    "check_in": {
                        "type": "string",
                        "description": "Check-in date in YYYY-MM-DD format (defaults to tomorrow if omitted)"
                    },
                    "check_out": {
                        "type": "string",
                        "description": "Check-out date in YYYY-MM-DD format (defaults to 2 days after check-in if omitted)"
                    },
                    "guests": {
                        "type": "integer",
                        "description": "Number of guests (default 1)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_resort_info",
            "description": "Get detailed information about Kaveri Stays properties, locations, amenities, and guest reviews.",
            "parameters": {
                "type": "object",
                "properties": {
                    "property_name_or_city": {
                        "type": "string",
                        "description": "Name or city of the property (Coorg, Ooty, Alleppey, or all)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "initiate_cancellation",
            "description": "Prepare a booking for cancellation, verify the guest owns it, inspect policy, and stage it for human confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "booking_id": {
                        "type": "integer",
                        "description": "ID of the booking the guest wishes to cancel"
                    },
                    "search_term": {
                        "type": "string",
                        "description": "Optional search term if booking ID is unknown (e.g. 'September 15', 'Coorg', 'pending')"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "confirm_cancellation",
            "description": "Execute the confirmed cancellation in the database after user explicit affirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "booking_id": {
                        "type": "integer",
                        "description": "ID of the booking to cancel"
                    }
                },
                "required": ["booking_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "initiate_booking",
            "description": "Prepare a room reservation for the guest, verify availability and pricing, and stage for confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "room_number": {
                        "type": "string",
                        "description": "Room number (e.g. '205', '302')"
                    },
                    "property_name_or_city": {
                        "type": "string",
                        "description": "Optional resort or city name (Coorg, Ooty, Alleppey)"
                    },
                    "check_in": {
                        "type": "string",
                        "description": "Check-in date in YYYY-MM-DD format"
                    },
                    "check_out": {
                        "type": "string",
                        "description": "Check-out date in YYYY-MM-DD format"
                    },
                    "guest_count": {
                        "type": "integer",
                        "description": "Number of guests (default 1)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "confirm_booking",
            "description": "Atomically finalize and create the room reservation and deposit in the database after user confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "room_id": {
                        "type": "integer",
                        "description": "Room ID to book"
                    },
                    "check_in": {
                        "type": "string",
                        "description": "Check-in date YYYY-MM-DD"
                    },
                    "check_out": {
                        "type": "string",
                        "description": "Check-out date YYYY-MM-DD"
                    },
                    "guest_count": {
                        "type": "integer",
                        "description": "Number of guests"
                    }
                },
                "required": ["room_id", "check_in", "check_out"]
            }
        }
    }
]
