from datetime import date, timedelta
from decimal import Decimal
from typing import List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models import Booking, Room, RoomType, Property, Rate, Payment
from app.exceptions import AppException, NotFoundException, UnprocessableException, ConflictException

def calculate_stay_pricing(db: Session, property_id: int, room_type_id: int, check_in: date, check_out: date) -> Tuple[Decimal, Decimal]:
    """
    Computes total stay pricing night-by-night from the rate table.
    Returns (nightly_rate_average, total_stay_amount).
    """
    if check_out <= check_in:
        raise UnprocessableException(message="Check-out date must be strictly after check-in date.")

    # Fetch rates covering the date range
    rates = db.query(Rate).filter(
        Rate.property_id == property_id,
        Rate.room_type_id == room_type_id,
        Rate.start_date <= check_out,
        Rate.end_date >= check_in
    ).all()

    total_nights = (check_out - check_in).days
    total_amount = Decimal("0.00")

    curr_date = check_in
    while curr_date < check_out:
        matched_rate = None
        for r in rates:
            if r.start_date <= curr_date <= r.end_date:
                matched_rate = r.nightly_rate
                break
        
        if matched_rate is None:
            # Fallback to default base rate if not explicitly in table
            matched_rate = Decimal("4000.00")
        
        total_amount += Decimal(str(matched_rate))
        curr_date += timedelta(days=1)

    avg_nightly_rate = total_amount / Decimal(str(total_nights))
    return avg_nightly_rate, total_amount

def get_booking_financials(db: Session, booking_id: int) -> Tuple[Decimal, Decimal]:
    """Returns (total_booking_cost, total_amount_paid)."""
    booking = db.query(Booking).filter(Booking.booking_id == booking_id).first()
    if not booking:
        return Decimal("0.00"), Decimal("0.00")

    room = db.query(Room).filter(Room.room_id == booking.room_id).first()
    _, total_cost = calculate_stay_pricing(db, room.property_id, room.room_type_id, booking.check_in, booking.check_out)

    payments = db.query(Payment).filter(Payment.booking_id == booking_id).all()
    total_paid = sum((Decimal(str(p.amount)) for p in payments), Decimal("0.00"))

    return total_cost, total_paid

def create_booking_atomic(
    db: Session,
    guest_id: int,
    room_id: int,
    check_in: date,
    check_out: date,
    guest_count: int,
    payment_method: str
) -> Booking:
    """
    Creates a booking and initial deposit in ONE atomic transaction.
    If payment insert or trigger fails, the entire transaction is rolled back.
    """
    if check_out <= check_in:
        raise UnprocessableException(message="Check-out date must be after check-in date.")

    room = db.query(Room).filter(Room.room_id == room_id).first()
    if not room:
        raise NotFoundException(message="Room not found.")

    # Calculate pricing
    avg_rate, total_amount = calculate_stay_pricing(db, room.property_id, room.room_type_id, check_in, check_out)

    # 1. Insert booking
    new_booking = Booking(
        guest_id=guest_id,
        room_id=room_id,
        check_in=check_in,
        check_out=check_out,
        guest_count=guest_count,
        status="confirmed"
    )
    db.add(new_booking)
    db.flush()  # Triggers database exclusion constraints and PL/pgSQL triggers

    # 2. Insert initial deposit payment (20% deposit)
    deposit_amount = (total_amount * Decimal("0.20")).quantize(Decimal("0.01"))
    new_payment = Payment(
        booking_id=new_booking.booking_id,
        amount=deposit_amount,
        method=payment_method,
        payment_date=date.today()
    )
    db.add(new_payment)
    db.flush()

    db.commit()
    db.refresh(new_booking)
    return new_booking

def transition_booking_state(
    db: Session,
    booking_id: int,
    target_state: str,
    allowed_roles: List[str],
    current_user_role: str
) -> Booking:
    """
    Validates and performs booking state machine transitions.
    """
    booking = db.query(Booking).filter(Booking.booking_id == booking_id).first()
    if not booking:
        raise NotFoundException(message="Booking not found.")

    current_state = booking.status

    # Define legal state machine transitions
    valid_transitions = {
        "confirmed": ["checked_in", "cancelled", "no_show"],
        "checked_in": ["checked_out"],
        "checked_out": [],
        "cancelled": [],
        "no_show": []
    }

    if target_state not in valid_transitions.get(current_state, []):
        raise AppException(
            code="ILLEGAL_STATE_TRANSITION",
            message=f"Cannot transition booking from state '{current_state}' to '{target_state}'.",
            status_code=400
        )

    booking.status = target_state
    db.commit()
    db.refresh(booking)
    return booking
