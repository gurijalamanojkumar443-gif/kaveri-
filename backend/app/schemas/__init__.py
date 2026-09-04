from pydantic import BaseModel, ConfigDict, Field, EmailStr
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal

class ErrorDetail(BaseModel):
    loc: Optional[List[str]] = None
    msg: Optional[str] = None
    type: Optional[str] = None

class ErrorBody(BaseModel):
    code: str
    message: str
    details: List[ErrorDetail] = Field(default_factory=list)

class ErrorResponse(BaseModel):
    error: ErrorBody

class MessageResponse(BaseModel):
    message: str

# Auth Schemas
class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8)
    phone: Optional[str] = Field(default=None, max_length=20)
    city: Optional[str] = Field(default=None, max_length=50)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RefreshRequest(BaseModel):
    refresh_token: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 900

class AccountResponse(BaseModel):
    account_id: int
    name: str
    email: str
    role: str
    property_id: Optional[int] = None
    guest_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

# Property & Room Types
class RoomTypeResponse(BaseModel):
    room_type_id: int
    type_name: str
    max_occupancy: int

    model_config = ConfigDict(from_attributes=True)

class PropertyResponse(BaseModel):
    property_id: int
    name: str
    city: str
    stars: Optional[int] = None
    average_rating: Optional[float] = None
    total_reviews: Optional[int] = 0

    model_config = ConfigDict(from_attributes=True)

class PropertyDetailResponse(BaseModel):
    property_id: int
    name: str
    city: str
    stars: Optional[int] = None
    average_rating: Optional[float] = None
    total_reviews: Optional[int] = 0
    room_types: List[RoomTypeResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

class AvailableRoomResponse(BaseModel):
    room_id: int
    property_id: int
    property_name: Optional[str] = None
    property_city: Optional[str] = None
    room_number: str
    room_type_id: int
    type_name: str
    max_occupancy: int
    nightly_rate: float
    total_rate: float

    model_config = ConfigDict(from_attributes=True)

# Review Schemas
class CreateReviewRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None

class ReviewResponse(BaseModel):
    review_id: int
    booking_id: int
    rating: int
    comment: Optional[str] = None
    review_date: Optional[date] = None

    model_config = ConfigDict(from_attributes=True)

class PropertyReviewItem(BaseModel):
    review_id: int
    booking_id: int
    rating: int
    comment: Optional[str] = None
    review_date: Optional[date] = None
    guest_name: str
    guest_city: Optional[str] = None
    room_type_name: Optional[str] = None
    property_id: int
    property_name: str
    city: str

    model_config = ConfigDict(from_attributes=True)

class PropertyReviewsSummary(BaseModel):
    property_id: Optional[int] = None
    property_name: Optional[str] = None
    city: Optional[str] = None
    average_rating: float
    total_reviews: int
    rating_distribution: dict[int, int]
    reviews: List[PropertyReviewItem] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

class ResortReviewCard(BaseModel):
    property_id: int
    property_name: str
    city: str
    stars: Optional[int] = None
    average_rating: float
    total_reviews: int
    top_comment: Optional[str] = None

class ChainReviewStatsResponse(BaseModel):
    overall_average_rating: float
    total_reviews: int
    resorts: List[ResortReviewCard]
    recent_reviews: List[PropertyReviewItem]

# Booking Schemas
class CreateBookingRequest(BaseModel):
    guest_id: Optional[int] = None
    room_id: int
    check_in: date
    check_out: date
    guest_count: int = Field(..., gt=0)
    payment_method: str = Field(default="card")

class BookingDetailResponse(BaseModel):
    booking_id: int
    guest_id: int
    guest_name: Optional[str] = None
    room_id: int
    room_number: Optional[str] = None
    property_name: Optional[str] = None
    check_in: date
    check_out: date
    guest_count: int
    status: str
    total_amount: float
    amount_paid: float
    review: Optional[ReviewResponse] = None

    model_config = ConfigDict(from_attributes=True)

class PaginatedBookingsResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[BookingDetailResponse]

# Payment Schemas
class CreatePaymentRequest(BaseModel):
    amount: Decimal = Field(..., gt=0)
    method: str = Field(..., min_length=1)

class PaymentResponse(BaseModel):
    payment_id: int
    booking_id: int
    amount: float
    method: str
    payment_date: date
    idempotency_key: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

# Report Schemas
class OccupancyReportResponse(BaseModel):
    property_id: int
    property_name: str
    total_rooms: int
    occupied_room_nights: int
    available_room_nights: int
    occupancy_percentage: float

class RevenueReportResponse(BaseModel):
    property_id: int
    property_name: str
    total_revenue: float
    adr: float
    revpar: float

# AI Agent Schemas
from app.schemas.agent import (
    ChatRequest,
    ChatResponse,
    ToolExecutionTrace,
    PendingActionDTO,
    ChatMessageDTO,
    AgentToolInfo
)

