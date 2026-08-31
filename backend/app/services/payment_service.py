from datetime import date
from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session
from app.models import Payment, Booking
from app.services.booking_service import get_booking_financials
from app.exceptions import NotFoundException, ConflictException, UnprocessableException, AppException

# In-memory idempotency store for payment retries
_idempotency_cache = {}

def process_payment(
    db: Session,
    booking_id: int,
    amount: Decimal,
    method: str,
    idempotency_key: Optional[str] = None
) -> Payment:
    """
    Records a payment against a booking with idempotency key deduplication.
    """
    if idempotency_key:
        if idempotency_key in _idempotency_cache:
            existing_payment_id = _idempotency_cache[idempotency_key]
            existing_payment = db.query(Payment).filter(Payment.payment_id == existing_payment_id).first()
            if existing_payment:
                return existing_payment

    booking = db.query(Booking).filter(Booking.booking_id == booking_id).first()
    if not booking:
        raise NotFoundException(message="Booking not found.")

    if booking.status in ["cancelled", "no_show"]:
        raise AppException(
            code="INVALID_BOOKING_STATUS",
            message=f"Cannot add payment to a booking with status '{booking.status}'.",
            status_code=400
        )

    # Check overpayment rule
    total_cost, total_paid = get_booking_financials(db, booking_id)
    if total_paid + amount > total_cost + Decimal("0.01"):
        raise AppException(
            code="PAYMENT_EXCEEDS_TOTAL",
            message=f"Payment amount of ₹{amount} exceeds remaining booking balance of ₹{max(Decimal('0.00'), total_cost - total_paid)}.",
            status_code=400
        )

    new_payment = Payment(
        booking_id=booking_id,
        amount=amount,
        method=method,
        payment_date=date.today()
    )
    db.add(new_payment)
    db.commit()
    db.refresh(new_payment)

    if idempotency_key:
        _idempotency_cache[idempotency_key] = new_payment.payment_id

    return new_payment
