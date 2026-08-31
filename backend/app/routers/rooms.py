from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.models import Room, RoomType, Property
from app.schemas import AvailableRoomResponse, ErrorResponse
from app.services.booking_service import calculate_stay_pricing
from app.exceptions import NotFoundException, UnprocessableException

router = APIRouter(prefix="/rooms", tags=["Rooms"])

@router.get(
    "/availability",
    response_model=List[AvailableRoomResponse],
    status_code=status.HTTP_200_OK,
    summary="Check room availability for given dates",
    description="Returns available rooms that do not have overlapping active bookings for the specified date range.",
    responses={
        200: {"model": List[AvailableRoomResponse], "description": "Available rooms returned successfully"},
        400: {"model": ErrorResponse, "description": "Invalid date range"},
        404: {"model": ErrorResponse, "description": "Property not found"}
    }
)
def check_availability(
    property_id: int = Query(..., description="Property ID"),
    check_in: date = Query(..., description="Check-in date (YYYY-MM-DD)"),
    check_out: date = Query(..., description="Check-out date (YYYY-MM-DD)"),
    room_type_id: Optional[int] = Query(None, description="Optional Room Type ID"),
    db: Session = Depends(get_db)
):
    if check_out <= check_in:
        raise UnprocessableException(message="Check-out date must be after check-in date.")

    prop = db.query(Property).filter(Property.property_id == property_id).first()
    if not prop:
        raise NotFoundException(message=f"Property with ID {property_id} not found.")

    # SQL query using GiST range exclusion logic and NOT EXISTS to find unbooked/available rooms
    sql = """
    SELECT
        r.room_id,
        r.property_id,
        r.room_number,
        r.room_type_id,
        rt.type_name,
        rt.max_occupancy
    FROM room r
    JOIN room_type rt ON rt.room_type_id = r.room_type_id
    WHERE r.property_id = :prop_id
      AND (:rt_id IS NULL OR r.room_type_id = :rt_id)
      AND NOT EXISTS (
          SELECT 1
          FROM booking b
          WHERE b.room_id = r.room_id
            AND b.status NOT IN ('cancelled', 'no_show')
            AND daterange(b.check_in, b.check_out, '[)') && daterange(:c_in, :c_out, '[)')
      )
    ORDER BY r.room_number;
    """

    rows = db.execute(
        text(sql),
        {
            "prop_id": property_id,
            "rt_id": room_type_id,
            "c_in": check_in,
            "c_out": check_out
        }
    ).fetchall()

    results = []
    for row in rows:
        room_id, p_id, room_num, r_type_id, type_name, max_occ = row
        avg_rate, total_rate = calculate_stay_pricing(db, p_id, r_type_id, check_in, check_out)
        results.append(AvailableRoomResponse(
            room_id=room_id,
            property_id=p_id,
            room_number=room_num,
            room_type_id=r_type_id,
            type_name=type_name,
            max_occupancy=max_occ,
            nightly_rate=float(avg_rate),
            total_rate=float(total_rate)
        ))

    return results
