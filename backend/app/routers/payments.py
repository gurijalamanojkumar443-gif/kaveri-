from typing import List, Optional
from fastapi import APIRouter, Depends, Header, Path, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Payment, Booking, Room, Account
from app.schemas import CreatePaymentRequest, PaymentResponse, ErrorResponse
from app.services.payment_service import process_payment
from app.dependencies import get_current_user
from app.exceptions import NotFoundException, ForbiddenException

router = APIRouter(prefix="/bookings", tags=["Payments"])

@router.get(
    "/{id}/payments",
    response_model=List[PaymentResponse],
    status_code=status.HTTP_200_OK,
    summary="Get all payments recorded for a booking",
    responses={
        200: {"model": List[PaymentResponse], "description": "List of payments"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        404: {"model": ErrorResponse, "description": "Booking not found"}
    }
)
def get_booking_payments(
    id: int = Path(..., description="Booking ID"),
    current_user: Account = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    booking = db.query(Booking).filter(Booking.booking_id == id).first()
    if not booking:
        raise NotFoundException(message=f"Booking with ID {id} not found.")

    room = db.query(Room).filter(Room.room_id == booking.room_id).first()

    # Scope checks
    if current_user.role == "guest" and booking.guest_id != current_user.guest_id:
        raise NotFoundException(message=f"Booking with ID {id} not found.")
    if current_user.role in ["staff", "manager"] and room.property_id != current_user.property_id:
        raise ForbiddenException(message="Access denied: booking belongs to another property.")

    payments = db.query(Payment).filter(Payment.booking_id == id).order_by(Payment.payment_id).all()
    return [
        PaymentResponse(
            payment_id=p.payment_id,
            booking_id=p.booking_id,
            amount=float(p.amount),
            method=p.method,
            payment_date=p.payment_date,
            idempotency_key=None
        )
        for p in payments
    ]

@router.post(
    "/{id}/payments",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a payment against a booking",
    description="Supports partial instalment payments and Idempotency-Key deduplication.",
    responses={
        201: {"model": PaymentResponse, "description": "Payment recorded successfully"},
        400: {"model": ErrorResponse, "description": "Payment exceeds booking total or invalid status"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        404: {"model": ErrorResponse, "description": "Booking not found"}
    }
)
def create_payment_for_booking(
    req: CreatePaymentRequest,
    id: int = Path(..., description="Booking ID"),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    current_user: Account = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    booking = db.query(Booking).filter(Booking.booking_id == id).first()
    if not booking:
        raise NotFoundException(message=f"Booking with ID {id} not found.")

    room = db.query(Room).filter(Room.room_id == booking.room_id).first()

    # Scope check
    if current_user.role == "guest" and booking.guest_id != current_user.guest_id:
        raise NotFoundException(message=f"Booking with ID {id} not found.")
    if current_user.role in ["staff", "manager"] and room.property_id != current_user.property_id:
        raise ForbiddenException(message="Access denied: booking belongs to another property.")

    payment = process_payment(
        db=db,
        booking_id=id,
        amount=req.amount,
        method=req.method,
        idempotency_key=idempotency_key
    )

    return PaymentResponse(
        payment_id=payment.payment_id,
        booking_id=payment.booking_id,
        amount=float(payment.amount),
        method=payment.method,
        payment_date=payment.payment_date,
        idempotency_key=idempotency_key
    )
