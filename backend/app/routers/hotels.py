from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Property, RoomType, Room
from app.schemas import PropertyResponse, PropertyDetailResponse, RoomTypeResponse, ErrorResponse
from app.exceptions import NotFoundException

router = APIRouter(prefix="/properties", tags=["Properties"])

@router.get(
    "",
    response_model=List[PropertyResponse],
    status_code=status.HTTP_200_OK,
    summary="List all Kaveri Stays properties",
    responses={
        200: {"model": List[PropertyResponse], "description": "Properties retrieved successfully"}
    }
)
def list_properties(db: Session = Depends(get_db)):
    properties = db.query(Property).order_by(Property.property_id).all()
    return properties

@router.get(
    "/{id}",
    response_model=PropertyDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get property details by ID",
    responses={
        200: {"model": PropertyDetailResponse, "description": "Property details retrieved"},
        404: {"model": ErrorResponse, "description": "Property not found"}
    }
)
def get_property(id: int, db: Session = Depends(get_db)):
    prop = db.query(Property).filter(Property.property_id == id).first()
    if not prop:
        raise NotFoundException(message=f"Property with ID {id} not found.")

    # Get room types available at this property
    room_types = db.query(RoomType).join(Room, Room.room_type_id == RoomType.room_type_id).filter(
        Room.property_id == id
    ).distinct().all()

    return PropertyDetailResponse(
        property_id=prop.property_id,
        name=prop.name,
        city=prop.city,
        stars=prop.stars,
        room_types=[RoomTypeResponse(
            room_type_id=rt.room_type_id,
            type_name=rt.type_name,
            max_occupancy=rt.max_occupancy
        ) for rt in room_types]
    )
