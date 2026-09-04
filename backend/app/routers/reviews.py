from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import Review, Booking, Guest, Room, Property, RoomType, Account
from app.schemas import (
    CreateReviewRequest,
    ReviewResponse,
    PropertyReviewItem,
    PropertyReviewsSummary,
    ResortReviewCard,
    ChainReviewStatsResponse,
    ErrorResponse
)
from app.dependencies import get_current_user
from app.exceptions import NotFoundException, AppException, ConflictException

router = APIRouter(tags=["Reviews"])


def _build_review_item(rev: Review, b: Booking, g: Guest, rm: Room, p: Property, rt: Optional[RoomType]) -> PropertyReviewItem:
    return PropertyReviewItem(
        review_id=rev.review_id,
        booking_id=rev.booking_id,
        rating=rev.rating,
        comment=rev.comment,
        review_date=rev.review_date,
        guest_name=g.name if g else "Guest",
        guest_city=g.city if g else None,
        room_type_name=rt.type_name if rt else None,
        property_id=p.property_id if p else 0,
        property_name=p.name if p else "Kaveri Stays",
        city=p.city if p else ""
    )


@router.post(
    "/bookings/{id}/review",
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


@router.get(
    "/properties/{id}/reviews",
    response_model=PropertyReviewsSummary,
    status_code=status.HTTP_200_OK,
    summary="Get all guest reviews and rating breakdown for a specific resort",
    description="Public endpoint returning calculated rating average, distribution, and verified guest reviews."
)
def get_property_reviews(
    id: int = Path(..., description="Property / Resort ID"),
    rating: Optional[int] = Query(None, ge=1, le=5, description="Filter by star rating"),
    limit: int = Query(50, ge=1, le=100, description="Max reviews to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db)
):
    prop = db.query(Property).filter(Property.property_id == id).first()
    if not prop:
        raise NotFoundException(message=f"Property with ID {id} not found.")

    # Base query for all reviews belonging to this property
    base_query = (
        db.query(Review, Booking, Guest, Room, Property, RoomType)
        .join(Booking, Review.booking_id == Booking.booking_id)
        .join(Guest, Booking.guest_id == Guest.guest_id)
        .join(Room, Booking.room_id == Room.room_id)
        .join(Property, Room.property_id == Property.property_id)
        .outerjoin(RoomType, Room.room_type_id == RoomType.room_type_id)
        .filter(Property.property_id == id)
    )

    all_property_reviews = base_query.all()
    total_reviews = len(all_property_reviews)

    # Compute rating distribution
    rating_distribution = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
    total_score = 0
    for rev, _, _, _, _, _ in all_property_reviews:
        if 1 <= rev.rating <= 5:
            rating_distribution[rev.rating] += 1
            total_score += rev.rating

    avg_rating = round(total_score / total_reviews, 1) if total_reviews > 0 else float(prop.stars or 5.0)

    # Apply rating filter if requested
    filtered_query = base_query
    if rating is not None:
        filtered_query = filtered_query.filter(Review.rating == rating)

    items_tuples = filtered_query.order_by(Review.review_id.desc()).offset(offset).limit(limit).all()
    review_items = [_build_review_item(rev, b, g, rm, p, rt) for rev, b, g, rm, p, rt in items_tuples]

    return PropertyReviewsSummary(
        property_id=prop.property_id,
        property_name=prop.name,
        city=prop.city,
        average_rating=avg_rating,
        total_reviews=total_reviews,
        rating_distribution=rating_distribution,
        reviews=review_items
    )


@router.get(
    "/reviews",
    response_model=PropertyReviewsSummary,
    status_code=status.HTTP_200_OK,
    summary="List guest reviews across all resorts",
    description="Public endpoint with optional property_id and rating filters."
)
def list_all_reviews(
    property_id: Optional[int] = Query(None, description="Filter by resort"),
    rating: Optional[int] = Query(None, ge=1, le=5, description="Filter by star rating"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    query = (
        db.query(Review, Booking, Guest, Room, Property, RoomType)
        .join(Booking, Review.booking_id == Booking.booking_id)
        .join(Guest, Booking.guest_id == Guest.guest_id)
        .join(Room, Booking.room_id == Room.room_id)
        .join(Property, Room.property_id == Property.property_id)
        .outerjoin(RoomType, Room.room_type_id == RoomType.room_type_id)
    )

    if property_id is not None:
        query = query.filter(Property.property_id == property_id)

    all_matched = query.all()
    total_reviews = len(all_matched)

    rating_distribution = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
    total_score = 0
    for rev, _, _, _, _, _ in all_matched:
        if 1 <= rev.rating <= 5:
            rating_distribution[rev.rating] += 1
            total_score += rev.rating

    avg_rating = round(total_score / total_reviews, 1) if total_reviews > 0 else 5.0

    filtered_query = query
    if rating is not None:
        filtered_query = filtered_query.filter(Review.rating == rating)

    items_tuples = filtered_query.order_by(Review.review_id.desc()).offset(offset).limit(limit).all()
    review_items = [_build_review_item(rev, b, g, rm, p, rt) for rev, b, g, rm, p, rt in items_tuples]

    prop_name = None
    prop_city = None
    if property_id is not None:
        prop = db.query(Property).filter(Property.property_id == property_id).first()
        if prop:
            prop_name = prop.name
            prop_city = prop.city

    return PropertyReviewsSummary(
        property_id=property_id,
        property_name=prop_name,
        city=prop_city,
        average_rating=avg_rating,
        total_reviews=total_reviews,
        rating_distribution=rating_distribution,
        reviews=review_items
    )


@router.get(
    "/reviews/stats",
    response_model=ChainReviewStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Review statistics across all resorts",
    description="Returns aggregate ratings, per-resort breakdown cards, and recent highlighted guest testimonials."
)
def get_review_stats(db: Session = Depends(get_db)):
    properties = db.query(Property).order_by(Property.property_id).all()
    resort_cards: List[ResortReviewCard] = []

    grand_total_reviews = 0
    grand_total_score = 0

    for p in properties:
        revs = (
            db.query(Review)
            .join(Booking, Review.booking_id == Booking.booking_id)
            .join(Room, Booking.room_id == Room.room_id)
            .filter(Room.property_id == p.property_id)
            .all()
        )
        p_total = len(revs)
        p_score = sum(r.rating for r in revs if r.rating)
        p_avg = round(p_score / p_total, 1) if p_total > 0 else float(p.stars or 5.0)

        grand_total_reviews += p_total
        grand_total_score += p_score

        # Find a top comment for the card
        top_rev = next((r.comment for r in revs if r.rating == 5 and r.comment), None)
        if not top_rev and revs:
            top_rev = revs[0].comment

        resort_cards.append(
            ResortReviewCard(
                property_id=p.property_id,
                property_name=p.name,
                city=p.city,
                stars=p.stars,
                average_rating=p_avg,
                total_reviews=p_total,
                top_comment=top_rev
            )
        )

    overall_avg = round(grand_total_score / grand_total_reviews, 1) if grand_total_reviews > 0 else 4.9

    # Recent reviews
    recent_tuples = (
        db.query(Review, Booking, Guest, Room, Property, RoomType)
        .join(Booking, Review.booking_id == Booking.booking_id)
        .join(Guest, Booking.guest_id == Guest.guest_id)
        .join(Room, Booking.room_id == Room.room_id)
        .join(Property, Room.property_id == Property.property_id)
        .outerjoin(RoomType, Room.room_type_id == RoomType.room_type_id)
        .order_by(Review.review_id.desc())
        .limit(10)
        .all()
    )
    recent_items = [_build_review_item(rev, b, g, rm, p, rt) for rev, b, g, rm, p, rt in recent_tuples]

    return ChainReviewStatsResponse(
        overall_average_rating=overall_avg,
        total_reviews=grand_total_reviews,
        resorts=resort_cards,
        recent_reviews=recent_items
    )
