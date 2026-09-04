"""
Database tools for Kaveri AI Agent.
Every tool enforces strict guest-scoping to ensure tenant isolation and database safety.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_

from app.models import Booking, Room, RoomType, Property, Payment, Rate, Guest, Review
from app.services.booking_service import calculate_stay_pricing, get_booking_financials


def get_my_bookings(
    db: Session,
    guest_id: int,
    status: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Retrieve bookings strictly belonging to the authenticated guest.
    Optionally filter by status: confirmed, checked_in, checked_out, cancelled, pending.
    """
    query = (
        db.query(Booking, Room, RoomType, Property)
        .join(Room, Booking.room_id == Room.room_id)
        .join(RoomType, Room.room_type_id == RoomType.room_type_id)
        .join(Property, Room.property_id == Property.property_id)
        .filter(Booking.guest_id == guest_id)
    )

    if status and status.lower() not in ["all", "any", "none"]:
        query = query.filter(Booking.status == status.lower())

    bookings = query.order_by(Booking.check_in.desc()).all()

    results = []
    for b, r, rt, p in bookings:
        cost, paid = get_booking_financials(db, b.booking_id)
        balance = max(Decimal("0.00"), cost - paid)
        results.append({
            "booking_id": b.booking_id,
            "property_name": p.name,
            "city": p.city,
            "room_number": r.room_number,
            "room_type": rt.type_name,
            "check_in": b.check_in.strftime("%Y-%m-%d"),
            "check_out": b.check_out.strftime("%Y-%m-%d"),
            "nights": (b.check_out - b.check_in).days,
            "guest_count": b.guest_count,
            "status": b.status,
            "total_cost": float(cost),
            "total_paid": float(paid),
            "balance_due": float(balance),
            "payment_status": "Paid" if balance <= Decimal("0.00") else ("Partially Paid" if paid > Decimal("0.00") else "Unpaid")
        })

    return results


def get_pending_bookings(
    db: Session,
    guest_id: int
) -> List[Dict[str, Any]]:
    """
    Retrieve bookings that are either in 'pending' status or have an unpaid balance.
    """
    all_bookings = get_my_bookings(db, guest_id=guest_id)
    pending_list = [
        b for b in all_bookings
        if b["status"] == "pending" or (b["status"] in ["confirmed", "checked_in"] and b["balance_due"] > 0)
    ]
    return pending_list


def calculate_total_spending(
    db: Session,
    guest_id: int,
    year: Optional[int] = None,
    property_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Calculate the total booking cost, amount paid, and balance due for the guest.
    Supports optional filtering by year and property name/city.
    """
    query = (
        db.query(Booking, Room, Property)
        .join(Room, Booking.room_id == Room.room_id)
        .join(Property, Room.property_id == Property.property_id)
        .filter(Booking.guest_id == guest_id)
        .filter(Booking.status != "cancelled")
    )

    if year:
        query = query.filter(func.extract('year', Booking.check_in) == year)

    if property_name:
        clean_prop = f"%{property_name.strip()}%"
        query = query.filter(or_(Property.name.ilike(clean_prop), Property.city.ilike(clean_prop)))

    bookings = query.all()

    total_cost = Decimal("0.00")
    total_paid = Decimal("0.00")
    property_breakdown: Dict[str, Dict[str, Any]] = {}

    for b, r, p in bookings:
        cost, paid = get_booking_financials(db, b.booking_id)
        total_cost += cost
        total_paid += paid

        if p.name not in property_breakdown:
            property_breakdown[p.name] = {"bookings_count": 0, "total_cost": 0.0, "total_paid": 0.0}
        property_breakdown[p.name]["bookings_count"] += 1
        property_breakdown[p.name]["total_cost"] += float(cost)
        property_breakdown[p.name]["total_paid"] += float(paid)

    return {
        "guest_id": guest_id,
        "filter_year": year,
        "filter_property": property_name,
        "total_bookings": len(bookings),
        "total_cost": float(total_cost),
        "total_paid": float(total_paid),
        "total_balance_due": float(max(Decimal("0.00"), total_cost - total_paid)),
        "property_breakdown": property_breakdown
    }


def search_available_rooms(
    db: Session,
    property_name_or_city: Optional[str] = None,
    check_in: Optional[str] = None,
    check_out: Optional[str] = None,
    guests: int = 1
) -> List[Dict[str, Any]]:
    """
    Search available rooms matching dates and guest capacity.
    """
    # Default dates if not specified
    today = date.today()
    if not check_in:
        c_in = today + timedelta(days=1)
    else:
        try:
            c_in = datetime.strptime(check_in.strip(), "%Y-%m-%d").date()
        except ValueError:
            c_in = today + timedelta(days=1)

    if not check_out:
        c_out = c_in + timedelta(days=2)
    else:
        try:
            c_out = datetime.strptime(check_out.strip(), "%Y-%m-%d").date()
        except ValueError:
            c_out = c_in + timedelta(days=2)

    if c_out <= c_in:
        c_out = c_in + timedelta(days=1)

    nights = (c_out - c_in).days

    # Subquery of conflicting booked rooms
    conflict_subq = (
        db.query(Booking.room_id)
        .filter(
            Booking.status.in_(["confirmed", "checked_in"]),
            Booking.check_in < c_out,
            Booking.check_out > c_in
        )
        .subquery()
    )

    query = (
        db.query(Room, RoomType, Property)
        .join(RoomType, Room.room_type_id == RoomType.room_type_id)
        .join(Property, Room.property_id == Property.property_id)
        .filter(~Room.room_id.in_(conflict_subq.select()))
        .filter(RoomType.max_occupancy >= guests)
    )

    if property_name_or_city and property_name_or_city.lower() not in ["all", "any"]:
        term = f"%{property_name_or_city.strip()}%"
        query = query.filter(or_(Property.name.ilike(term), Property.city.ilike(term)))

    available_rooms = query.all()

    results = []
    for r, rt, p in available_rooms:
        avg_rate, total_rate = calculate_stay_pricing(db, p.property_id, rt.room_type_id, c_in, c_out)
        results.append({
            "room_id": r.room_id,
            "room_number": r.room_number,
            "property_id": p.property_id,
            "property_name": p.name,
            "city": p.city,
            "room_type": rt.type_name,
            "max_occupancy": rt.max_occupancy,
            "check_in": c_in.strftime("%Y-%m-%d"),
            "check_out": c_out.strftime("%Y-%m-%d"),
            "nights": nights,
            "nightly_rate": float(avg_rate),
            "total_rate": float(total_rate)
        })

    return results


def get_resort_info(
    db: Session,
    property_name_or_city: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get detailed property information, ratings, and highlights.
    """
    query = db.query(Property)
    if property_name_or_city and property_name_or_city.lower() not in ["all", "any"]:
        term = f"%{property_name_or_city.strip()}%"
        query = query.filter(or_(Property.name.ilike(term), Property.city.ilike(term)))

    properties = query.all()

    meta_descriptions = {
        1: {
            "tagline": "A serene sanctuary perched along the gentle bends of the river.",
            "amenities": ["Infinity Riverside Pool", "Coffee Plantation Walk", "Ayurvedic Spa", "Open-hearth Dining", "Kayaking"],
            "location": "Madikeri, Coorg, Karnataka"
        },
        2: {
            "tagline": "Colonial-era luxury amidst whispering pines and tea terraces.",
            "amenities": ["Heated Indoor Pool", "Heritage Tea Lounge", "Equestrian Trails", "Mountain View Jacuzzis", "Bonfire Soirées"],
            "location": "Upper Nilgiris, Ooty, Tamil Nadu"
        },
        3: {
            "tagline": "Traditional Kerala architectural splendor overlooking calm backwaters.",
            "amenities": ["Private Houseboat Cruises", "Lotus Lagoon Spa", "Coastal Seafood Pavilion", "Sunset Deck Yoga", "Canoeing"],
            "location": "Punnamada, Alleppey, Kerala"
        }
    }

    results = []
    for p in properties:
        rev_count = db.query(Review).join(Booking).join(Room).filter(Room.property_id == p.property_id).count()
        avg_rating = db.query(func.avg(Review.rating)).join(Booking).join(Room).filter(Room.property_id == p.property_id).scalar() or 4.85

        info = meta_descriptions.get(p.property_id, {
            "tagline": "Eco-luxury sanctuary by Kaveri Stays.",
            "amenities": ["Spa", "Fine Dining", "Concierge"],
            "location": p.city
        })

        results.append({
            "property_id": p.property_id,
            "name": p.name,
            "city": p.city,
            "stars": p.stars,
            "tagline": info["tagline"],
            "amenities": info["amenities"],
            "location": info["location"],
            "average_rating": round(float(avg_rating), 1),
            "review_count": rev_count
        })

    return results


def initiate_cancellation(
    db: Session,
    guest_id: int,
    booking_id: Optional[int] = None,
    search_term: Optional[str] = None
) -> Dict[str, Any]:
    """
    Validates a cancellation candidate for the guest, checks policy, and creates a staging payload for user confirmation.
    Does NOT cancel the booking yet.
    """
    # 1. Locate target booking
    query = (
        db.query(Booking, Room, RoomType, Property)
        .join(Room, Booking.room_id == Room.room_id)
        .join(RoomType, Room.room_type_id == RoomType.room_type_id)
        .join(Property, Room.property_id == Property.property_id)
        .filter(Booking.guest_id == guest_id)
    )

    if booking_id:
        target = query.filter(Booking.booking_id == booking_id).first()
    else:
        # Check if search term contains specific property or date
        matched_target = None
        if search_term:
            lower_st = search_term.lower()
            for kw, prop_filter in [("coorg", "Coorg"), ("ooty", "Ooty"), ("alleppey", "Alleppey"), ("riverside", "Riverside"), ("hilltop", "Hilltop"), ("backwater", "Backwater")]:
                if kw in lower_st:
                    matched_target = query.filter(
                        Booking.status.in_(["confirmed", "pending"]),
                        or_(Property.name.ilike(f"%{prop_filter}%"), Property.city.ilike(f"%{prop_filter}%"))
                    ).order_by(Booking.check_in.desc()).first()
                    break
        
        target = matched_target or query.filter(Booking.status.in_(["confirmed", "pending"])).order_by(Booking.check_in.desc()).first()

    if not target:
        return {
            "success": False,
            "error": "No eligible booking found for cancellation."
        }

    b, r, rt, p = target

    if b.status == "cancelled":
        return {
            "success": False,
            "error": f"Booking #{b.booking_id} at {p.name} is already cancelled."
        }

    if b.status in ["checked_in", "checked_out"]:
        return {
            "success": False,
            "error": f"Booking #{b.booking_id} is currently {b.status} and cannot be cancelled online. Please contact resort front desk."
        }

    cost, paid = get_booking_financials(db, b.booking_id)

    # Cancellation policy: Full refund if > 48h before check-in, else 1 night fee
    days_to_checkin = (b.check_in - date.today()).days
    if days_to_checkin >= 2:
        refund_amount = paid
        policy_note = "Eligible for 100% full refund under 48-hour free cancellation policy."
    else:
        # 1-night fee or 50%
        penalty = min(paid, Decimal("2000.00"))
        refund_amount = max(Decimal("0.00"), paid - penalty)
        policy_note = "Late cancellation (< 48 hours). A standard ₹2,000 reservation fee applies."

    return {
        "success": True,
        "booking_id": b.booking_id,
        "property_name": p.name,
        "city": p.city,
        "room_type": rt.type_name,
        "check_in": b.check_in.strftime("%Y-%m-%d"),
        "check_out": b.check_out.strftime("%Y-%m-%d"),
        "total_cost": float(cost),
        "total_paid": float(paid),
        "estimated_refund": float(refund_amount),
        "policy_note": policy_note,
        "requires_confirmation": True,
        "confirmation_prompt": (
            f"I found Booking #{b.booking_id} for {p.name} ({b.check_in.strftime('%b %d')} – {b.check_out.strftime('%b %d, %Y')}). "
            f"{policy_note} Refund amount: ₹{refund_amount:,.2f}.\n\n"
            f"Are you sure you would like to proceed with cancelling Booking #{b.booking_id}?"
        )
    }


def confirm_cancellation(
    db: Session,
    guest_id: int,
    booking_id: int
) -> Dict[str, Any]:
    """
    Executes the actual cancellation in the database after user confirmation.
    """
    booking = (
        db.query(Booking)
        .filter(Booking.booking_id == booking_id, Booking.guest_id == guest_id)
        .first()
    )

    if not booking:
        return {
            "success": False,
            "error": f"Booking #{booking_id} not found or you are not authorized to cancel it."
        }

    if booking.status == "cancelled":
        return {
            "success": True,
            "booking_id": booking_id,
            "status": "cancelled",
            "message": f"Booking #{booking_id} was already cancelled."
        }

    booking.status = "cancelled"
    db.commit()
    db.refresh(booking)

    return {
        "success": True,
        "booking_id": booking.booking_id,
        "status": "cancelled",
        "message": f"✦ Booking #{booking.booking_id} has been cancelled successfully. Your room has been released."
    }
