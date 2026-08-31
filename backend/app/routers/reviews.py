from datetime import date
from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Review, Booking, Account
from app.schemas import CreateReviewRequest, ReviewResponse, ErrorResponse
from app.dependencies import get_current_user
from app.exceptions import NotFoundException, ForbiddenException, AppException, ConflictException

router = APIRouter(prefix="/bookings", tags=["Reviews"])

@router.post(
    "/{id}/review",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a review for a completed stay",
    description="Allowed only after booking status is 'checked_out'. Strictly one review per booking stay.",
    responses={
        201: {"model": ReviewResponse, "description": "Review created successfully"},
        400: {"model": ErrorResponse, "description": "Stay is not checked out yet"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden - Not your booking"},
        404: {"model": ErrorResponse, "description": "Booking not found"},
        409: {"model": ErrorResponse, "description": "Review already submitted for this booking"},
        422: {"model": ErrorResponse, "description": "Rating outside 1 to 5"}
    }
)
def create_review_for_booking(
    req: CreateReviewRequest,
    id: int = Path(..., description="Booking ID"),
    current_user: Account = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    booking = db.query(Booking).filter(Booking.booking_id == id).first()
    if not booking:
        raise NotFoundException(message=f"Booking with ID {id} not found.")

    # Ownership check
    if current_user.role == "guest" and booking.guest_id != current_user.guest_id:
        raise NotFoundException(message=f"Booking with ID {id} not found.")

    # Review lifecycle check: must be checked_out
    if booking.status != "checked_out":
        raise AppException(
            code="STAY_NOT_COMPLETED",
            message=f"Cannot post a review for a stay with status '{booking.status}'. Review requires 'checked_out'.",
            status_code=400
        )

    # Check for existing review
    existing = db.query(Review).filter(Review.booking_id == id).first()
    if existing:
        raise ConflictException(
            code="DUPLICATE_REVIEW",
            message="A review has already been submitted for this stay."
        )

    new_review = Review(
        booking_id=id,
        rating=req.rating,
        comment=req.comment,
        review_date=date.today()
    )
    db.add(new_review)
    db.commit()
    db.refresh(new_review)

    return ReviewResponse(
        review_id=new_review.review_id,
        booking_id=new_review.booking_id,
        rating=new_review.rating,
        comment=new_review.comment,
        review_date=new_review.review_date
    )
