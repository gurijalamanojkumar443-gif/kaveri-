from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Path, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.models import Booking, Room, Property, Guest, Account, Review
from app.schemas import (
    CreateBookingRequest, BookingDetailResponse, PaginatedBookingsResponse, ErrorResponse, ReviewResponse
)
from app.services.booking_service import (
    create_booking_atomic, get_booking_financials, transition_booking_state
)
from app.dependencies import (
    get_current_user, require_guest, require_staff, require_manager, enforce_property_scope
)
from app.exceptions import (
    NotFoundException, ForbiddenException, UnprocessableException, ConflictException, AppException
)

router = APIRouter(prefix="/bookings", tags=["Bookings"])

# Whitelist allowed sorting fields to prevent SQL injection
SORT_WHITELIST = {
    "check_in": "b.check_in",
    "check_out": "b.check_out",
    "booking_id": "b.booking_id",
    "guest_count": "b.guest_count"
}

@router.get(
    "",
    response_model=PaginatedBookingsResponse,
    status_code=status.HTTP_200_OK,
    summary="List bookings with filtering and sorting",
    description="Returns bookings scoped to the caller's role (guests see own, managers see property, owner sees all).",
    responses={
        200: {"model": PaginatedBookingsResponse, "description": "Bookings list retrieved"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"}
    }
)
def list_bookings(
    property_id: Optional[int] = Query(None, description="Filter by property ID"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by booking status"),
    start_date: Optional[date] = Query(None, description="Check-in on or after date"),
    end_date: Optional[date] = Query(None, description="Check-out on or before date"),
    guest_id: Optional[int] = Query(None, description="Filter by guest ID"),
    sort_by: str = Query("check_in", description="Field to sort by (check_in, check_out, booking_id, guest_count)"),
    sort_order: str = Query("desc", description="Sort direction (asc, desc)"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Page offset"),
    current_user: Account = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Validate sort parameter against whitelist
    if sort_by not in SORT_WHITELIST:
        sort_by = "check_in"
    sort_column = SORT_WHITELIST[sort_by]
    direction = "ASC" if sort_order.lower() == "asc" else "DESC"

    # Enforce role scoping
    effective_prop_id = None
    effective_guest_id = None

    if current_user.role == "guest":
        effective_guest_id = current_user.guest_id
        if not effective_guest_id:
            return PaginatedBookingsResponse(total=0, limit=limit, offset=offset, items=[])
    elif current_user.role in ["staff", "manager"]:
        effective_prop_id = current_user.property_id
        if property_id is not None and property_id != effective_prop_id:
            raise ForbiddenException(message=f"Access denied: cannot view bookings for property {property_id}.")
    elif current_user.role == "owner":
        effective_prop_id = property_id
        effective_guest_id = guest_id

    # Build SQL query safely with parameter bindings
    where_clauses = ["1=1"]
    params = {"limit": limit, "offset": offset}

    if effective_guest_id is not None:
        where_clauses.append("b.guest_id = :guest_id")
        params["guest_id"] = effective_guest_id

    if effective_prop_id is not None:
        where_clauses.append("r.property_id = :property_id")
        params["property_id"] = effective_prop_id

    if status_filter:
        where_clauses.append("b.status = :status")
        params["status"] = status_filter

    if start_date:
        where_clauses.append("b.check_in >= :start_date")
        params["start_date"] = start_date

    if end_date:
        where_clauses.append("b.check_out <= :end_date")
        params["end_date"] = end_date

    where_sql = " AND ".join(where_clauses)

    count_sql = f"""
    SELECT COUNT(*)
    FROM booking b
    JOIN room r ON r.room_id = b.room_id
    WHERE {where_sql}
    """
    total_count = db.execute(text(count_sql), params).scalar() or 0

    data_sql = f"""
    SELECT
        b.booking_id,
        b.guest_id,
        g.name AS guest_name,
        b.room_id,
        r.room_number,
        p.name AS property_name,
        b.check_in,
        b.check_out,
        b.guest_count,
        b.status
    FROM booking b
    JOIN guest g ON g.guest_id = b.guest_id
    JOIN room r ON r.room_id = b.room_id
    JOIN property p ON p.property_id = r.property_id
    WHERE {where_sql}
    ORDER BY {sort_column} {direction}
    LIMIT :limit OFFSET :offset
    """
    rows = db.execute(text(data_sql), params).fetchall()

    booking_ids = [r[0] for r in rows]
    reviews_map = {}
    if booking_ids:
        for rev in db.query(Review).filter(Review.booking_id.in_(booking_ids)).all():
            reviews_map[rev.booking_id] = ReviewResponse(
                review_id=rev.review_id,
                booking_id=rev.booking_id,
                rating=rev.rating,
                comment=rev.comment,
                review_date=rev.review_date
            )

    items = []
    for r in rows:
        b_id = r[0]
        total_cost, total_paid = get_booking_financials(db, b_id)
        items.append(BookingDetailResponse(
            booking_id=r[0],
            guest_id=r[1],
            guest_name=r[2],
            room_id=r[3],
            room_number=r[4],
            property_name=r[5],
            check_in=r[6],
            check_out=r[7],
            guest_count=r[8],
            status=r[9],
            total_amount=float(total_cost),
            amount_paid=float(total_paid),
            review=reviews_map.get(b_id)
        ))

    return PaginatedBookingsResponse(
        total=total_count,
        limit=limit,
        offset=offset,
        items=items
    )

@router.post(
    "",
    response_model=BookingDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new booking and record initial deposit",
    description="Atomically verifies room capacity, creates booking, and records deposit inside a single database transaction.",
    responses={
        201: {"model": BookingDetailResponse, "description": "Booking created successfully"},
        400: {"model": ErrorResponse, "description": "Invalid dates or parameters"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Room or guest not found"},
        409: {"model": ErrorResponse, "description": "Room already booked for requested dates"},
        422: {"model": ErrorResponse, "description": "Guest count exceeds maximum room occupancy"}
    }
)
def create_booking(
    req: CreateBookingRequest,
    current_user: Account = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Determine target guest_id
    if current_user.role == "guest":
        target_guest_id = current_user.guest_id
        if not target_guest_id:
            # Create or link guest profile
            g = db.query(Guest).filter(Guest.email == current_user.email).first()
            if not g:
                g = Guest(name=current_user.name, email=current_user.email)
                db.add(g)
                db.flush()
                current_user.guest_id = g.guest_id
                db.commit()
            target_guest_id = g.guest_id
    else:
        # Staff/manager/owner creating booking on behalf of a guest
        if req.guest_id:
            target_guest_id = req.guest_id
        elif current_user.guest_id:
            target_guest_id = current_user.guest_id
        else:
            target_guest_id = 1  # Fallback to demo guest

    booking = create_booking_atomic(
        db=db,
        guest_id=target_guest_id,
        room_id=req.room_id,
        check_in=req.check_in,
        check_out=req.check_out,
        guest_count=req.guest_count,
        payment_method=req.payment_method
    )

    room = db.query(Room).filter(Room.room_id == booking.room_id).first()
    prop = db.query(Property).filter(Property.property_id == room.property_id).first()
    guest = db.query(Guest).filter(Guest.guest_id == booking.guest_id).first()
    total_cost, total_paid = get_booking_financials(db, booking.booking_id)

    return BookingDetailResponse(
        booking_id=booking.booking_id,
        guest_id=booking.guest_id,
        guest_name=guest.name if guest else "Guest",
        room_id=booking.room_id,
        room_number=room.room_number if room else "N/A",
        property_name=prop.name if prop else "Kaveri Stays",
        check_in=booking.check_in,
        check_out=booking.check_out,
        guest_count=booking.guest_count,
        status=booking.status,
        total_amount=float(total_cost),
        amount_paid=float(total_paid)
    )

@router.get(
    "/{id}",
    response_model=BookingDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get booking details by ID",
    description="Returns booking details. For guest privacy, returns 404 if booking belongs to another guest.",
    responses={
        200: {"model": BookingDetailResponse, "description": "Booking details retrieved"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Booking not found"}
    }
)
def get_booking_by_id(
    id: int = Path(..., description="Booking ID"),
    current_user: Account = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    booking = db.query(Booking).filter(Booking.booking_id == id).first()
    if not booking:
        raise NotFoundException(message=f"Booking with ID {id} not found.")

    room = db.query(Room).filter(Room.room_id == booking.room_id).first()
    prop = db.query(Property).filter(Property.property_id == room.property_id).first()
    guest = db.query(Guest).filter(Guest.guest_id == booking.guest_id).first()

    # Privacy Protection:
    # A guest cannot see another guest's booking. We return 404 Not Found rather than 403 Forbidden
    # to avoid leaking the existence of other guests' booking IDs.
    if current_user.role == "guest" and booking.guest_id != current_user.guest_id:
        raise NotFoundException(message=f"Booking with ID {id} not found.")

    # Property scoping for staff and managers
    if current_user.role in ["staff", "manager"] and room.property_id != current_user.property_id:
        raise ForbiddenException(message="Access denied: this booking belongs to another property.")

    total_cost, total_paid = get_booking_financials(db, booking.booking_id)

    rev = db.query(Review).filter(Review.booking_id == booking.booking_id).first()
    review_resp = None
    if rev:
        review_resp = ReviewResponse(
            review_id=rev.review_id,
            booking_id=rev.booking_id,
            rating=rev.rating,
            comment=rev.comment,
            review_date=rev.review_date
        )

    return BookingDetailResponse(
        booking_id=booking.booking_id,
        guest_id=booking.guest_id,
        guest_name=guest.name if guest else "Guest",
        room_id=booking.room_id,
        room_number=room.room_number if room else "N/A",
        property_name=prop.name if prop else "Kaveri Stays",
        check_in=booking.check_in,
        check_out=booking.check_out,
        guest_count=booking.guest_count,
        status=booking.status,
        total_amount=float(total_cost),
        amount_paid=float(total_paid),
        review=review_resp
    )

@router.post(
    "/{id}/check-in",
    response_model=BookingDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Check-in a guest",
    description="Transitions booking status from 'confirmed' to 'checked_in'. Permitted for staff, manager, and owner.",
    responses={
        200: {"model": BookingDetailResponse, "description": "Check-in successful"},
        400: {"model": ErrorResponse, "description": "Illegal state transition"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden - Guests cannot perform check-in"},
        404: {"model": ErrorResponse, "description": "Booking not found"}
    }
)
def check_in_booking(
    id: int = Path(..., description="Booking ID"),
    current_user: Account = Depends(require_staff),
    db: Session = Depends(get_db)
):
    booking = db.query(Booking).filter(Booking.booking_id == id).first()
    if not booking:
        raise NotFoundException(message=f"Booking with ID {id} not found.")

    room = db.query(Room).filter(Room.room_id == booking.room_id).first()
    if current_user.role in ["staff", "manager"] and room.property_id != current_user.property_id:
        raise ForbiddenException(message="Access denied: booking belongs to another property.")

    updated_booking = transition_booking_state(
        db=db,
        booking_id=id,
        target_state="checked_in",
        allowed_roles=["staff", "manager", "owner"],
        current_user_role=current_user.role
    )

    prop = db.query(Property).filter(Property.property_id == room.property_id).first()
    guest = db.query(Guest).filter(Guest.guest_id == updated_booking.guest_id).first()
    total_cost, total_paid = get_booking_financials(db, updated_booking.booking_id)

    return BookingDetailResponse(
        booking_id=updated_booking.booking_id,
        guest_id=updated_booking.guest_id,
        guest_name=guest.name if guest else "Guest",
        room_id=updated_booking.room_id,
        room_number=room.room_number if room else "N/A",
        property_name=prop.name if prop else "Kaveri Stays",
        check_in=updated_booking.check_in,
        check_out=updated_booking.check_out,
        guest_count=updated_booking.guest_count,
        status=updated_booking.status,
        total_amount=float(total_cost),
        amount_paid=float(total_paid)
    )

@router.post(
    "/{id}/check-out",
    response_model=BookingDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Check-out a guest",
    description="Transitions booking status from 'checked_in' to 'checked_out'. Permitted for staff, manager, and owner.",
    responses={
        200: {"model": BookingDetailResponse, "description": "Check-out successful"},
        400: {"model": ErrorResponse, "description": "Illegal state transition"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden - Guests cannot perform check-out"},
        404: {"model": ErrorResponse, "description": "Booking not found"}
    }
)
def check_out_booking(
    id: int = Path(..., description="Booking ID"),
    current_user: Account = Depends(require_staff),
    db: Session = Depends(get_db)
):
    booking = db.query(Booking).filter(Booking.booking_id == id).first()
    if not booking:
        raise NotFoundException(message=f"Booking with ID {id} not found.")

    room = db.query(Room).filter(Room.room_id == booking.room_id).first()
    if current_user.role in ["staff", "manager"] and room.property_id != current_user.property_id:
        raise ForbiddenException(message="Access denied: booking belongs to another property.")

    updated_booking = transition_booking_state(
        db=db,
        booking_id=id,
        target_state="checked_out",
        allowed_roles=["staff", "manager", "owner"],
        current_user_role=current_user.role
    )

    prop = db.query(Property).filter(Property.property_id == room.property_id).first()
    guest = db.query(Guest).filter(Guest.guest_id == updated_booking.guest_id).first()
    total_cost, total_paid = get_booking_financials(db, updated_booking.booking_id)

    return BookingDetailResponse(
        booking_id=updated_booking.booking_id,
        guest_id=updated_booking.guest_id,
        guest_name=guest.name if guest else "Guest",
        room_id=updated_booking.room_id,
        room_number=room.room_number if room else "N/A",
        property_name=prop.name if prop else "Kaveri Stays",
        check_in=updated_booking.check_in,
        check_out=updated_booking.check_out,
        guest_count=updated_booking.guest_count,
        status=updated_booking.status,
        total_amount=float(total_cost),
        amount_paid=float(total_paid)
    )

@router.post(
    "/{id}/cancel",
    response_model=BookingDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel a booking",
    description="Transitions booking status from 'confirmed' to 'cancelled'.",
    responses={
        200: {"model": BookingDetailResponse, "description": "Cancellation successful"},
        400: {"model": ErrorResponse, "description": "Illegal state transition"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        404: {"model": ErrorResponse, "description": "Booking not found"}
    }
)
def cancel_booking(
    id: int = Path(..., description="Booking ID"),
    current_user: Account = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    booking = db.query(Booking).filter(Booking.booking_id == id).first()
    if not booking:
        raise NotFoundException(message=f"Booking with ID {id} not found.")

    room = db.query(Room).filter(Room.room_id == booking.room_id).first()

    # Permission check: Guest can cancel own booking; Manager for own property; Owner for any
    if current_user.role == "guest" and booking.guest_id != current_user.guest_id:
        raise NotFoundException(message=f"Booking with ID {id} not found.")
    if current_user.role == "manager" and room.property_id != current_user.property_id:
        raise ForbiddenException(message="Access denied: booking belongs to another property.")
    if current_user.role == "staff":
        raise ForbiddenException(message="Staff cannot cancel bookings; manager approval required.")

    updated_booking = transition_booking_state(
        db=db,
        booking_id=id,
        target_state="cancelled",
        allowed_roles=["guest", "manager", "owner"],
        current_user_role=current_user.role
    )

    prop = db.query(Property).filter(Property.property_id == room.property_id).first()
    guest = db.query(Guest).filter(Guest.guest_id == updated_booking.guest_id).first()
    total_cost, total_paid = get_booking_financials(db, updated_booking.booking_id)

    return BookingDetailResponse(
        booking_id=updated_booking.booking_id,
        guest_id=updated_booking.guest_id,
        guest_name=guest.name if guest else "Guest",
        room_id=updated_booking.room_id,
        room_number=room.room_number if room else "N/A",
        property_name=prop.name if prop else "Kaveri Stays",
        check_in=updated_booking.check_in,
        check_out=updated_booking.check_out,
        guest_count=updated_booking.guest_count,
        status=updated_booking.status,
        total_amount=float(total_cost),
        amount_paid=float(total_paid)
    )
