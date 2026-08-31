from sqlalchemy import Column, Integer, SmallInteger, String, Date, Numeric, Text, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Property(Base):
    __tablename__ = "property"

    property_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    city = Column(String(50), nullable=False)
    stars = Column(SmallInteger, nullable=True)

    rooms = relationship("Room", back_populates="property")
    rates = relationship("Rate", back_populates="property")
    accounts = relationship("Account", back_populates="property")

class RoomType(Base):
    __tablename__ = "room_type"

    room_type_id = Column(Integer, primary_key=True, index=True)
    type_name = Column(String(20), unique=True, nullable=False)
    max_occupancy = Column(SmallInteger, nullable=False)

    rooms = relationship("Room", back_populates="room_type")
    rates = relationship("Rate", back_populates="room_type")

class Guest(Base):
    __tablename__ = "guest"

    guest_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(20), nullable=True)
    city = Column(String(50), nullable=True)

    bookings = relationship("Booking", back_populates="guest")
    accounts = relationship("Account", back_populates="guest")

class Room(Base):
    __tablename__ = "room"

    room_id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("property.property_id"), nullable=False)
    room_number = Column(String(10), nullable=False)
    room_type_id = Column(Integer, ForeignKey("room_type.room_type_id"), nullable=False)

    property = relationship("Property", back_populates="rooms")
    room_type = relationship("RoomType", back_populates="rooms")
    bookings = relationship("Booking", back_populates="room")

class Booking(Base):
    __tablename__ = "booking"

    booking_id = Column(Integer, primary_key=True, index=True)
    guest_id = Column(Integer, ForeignKey("guest.guest_id"), nullable=False)
    room_id = Column(Integer, ForeignKey("room.room_id"), nullable=False)
    check_in = Column(Date, nullable=False)
    check_out = Column(Date, nullable=False)
    guest_count = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="confirmed")

    guest = relationship("Guest", back_populates="bookings")
    room = relationship("Room", back_populates="bookings")
    payments = relationship("Payment", back_populates="booking", cascade="all, delete-orphan")
    review = relationship("Review", back_populates="booking", uselist=False)

class Payment(Base):
    __tablename__ = "payment"

    payment_id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("booking.booking_id"), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    method = Column(String(20), nullable=False)
    payment_date = Column(Date, nullable=False)

    booking = relationship("Booking", back_populates="payments")

class Review(Base):
    __tablename__ = "review"

    review_id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("booking.booking_id"), unique=True, nullable=False)
    rating = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    review_date = Column(Date, nullable=True, default=func.current_date())

    booking = relationship("Booking", back_populates="review")

class Rate(Base):
    __tablename__ = "rate"

    rate_id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("property.property_id"), nullable=False)
    room_type_id = Column(Integer, ForeignKey("room_type.room_type_id"), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    nightly_rate = Column(Numeric(10, 2), nullable=False)

    property = relationship("Property", back_populates="rates")
    room_type = relationship("RoomType", back_populates="rates")

class Account(Base):
    __tablename__ = "account"

    account_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)
    property_id = Column(Integer, ForeignKey("property.property_id"), nullable=True)
    guest_id = Column(Integer, ForeignKey("guest.guest_id"), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    property = relationship("Property", back_populates="accounts")
    guest = relationship("Guest", back_populates="accounts")
    refresh_tokens = relationship("RefreshToken", back_populates="account", cascade="all, delete-orphan")

class RefreshToken(Base):
    __tablename__ = "refresh_token"

    token_id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("account.account_id"), nullable=False)
    token_hash = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, nullable=False, default=False)
    replaced_by = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    account = relationship("Account", back_populates="refresh_tokens")
