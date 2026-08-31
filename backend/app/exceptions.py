from fastapi import Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, DataError, InternalError, ProgrammingError
import re

class AppException(Exception):
    def __init__(self, code: str, message: str, status_code: int = status.HTTP_400_BAD_REQUEST, details: list = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or []

class UnauthorizedException(AppException):
    def __init__(self, message: str = "Invalid or missing authentication credentials", code: str = "UNAUTHORIZED"):
        super().__init__(code=code, message=message, status_code=status.HTTP_401_UNAUTHORIZED)

class ForbiddenException(AppException):
    def __init__(self, message: str = "You do not have permission to access this resource", code: str = "FORBIDDEN"):
        super().__init__(code=code, message=message, status_code=status.HTTP_403_FORBIDDEN)

class NotFoundException(AppException):
    def __init__(self, message: str = "The requested resource was not found", code: str = "NOT_FOUND"):
        super().__init__(code=code, message=message, status_code=status.HTTP_404_NOT_FOUND)

class ConflictException(AppException):
    def __init__(self, message: str = "The request conflicts with existing data", code: str = "CONFLICT"):
        super().__init__(code=code, message=message, status_code=status.HTTP_409_CONFLICT)

class UnprocessableException(AppException):
    def __init__(self, message: str = "The request data violates business rules", code: str = "UNPROCESSABLE_ENTITY"):
        super().__init__(code=code, message=message, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

def format_error_response(code: str, message: str, status_code: int, details: list = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details or []
            }
        }
    )

def handle_app_exception(request: Request, exc: AppException) -> JSONResponse:
    return format_error_response(
        code=exc.code,
        message=exc.message,
        status_code=exc.status_code,
        details=exc.details
    )

def handle_database_exception(request: Request, exc: Exception) -> JSONResponse:
    """
    Central Database Exception Handler.
    Translates raw PostgreSQL SQLSTATE codes into safe, non-leaking HTTP responses.
    """
    # Extract underlying psycopg2 pgcode if available
    orig = getattr(exc, "orig", exc)
    pgcode = getattr(orig, "pgcode", None)
    err_str = str(orig).lower()

    # 1. SQLSTATE 23P01: Exclusion Constraint Violation (Overlapping bookings or rates)
    if pgcode == "23P01" or "exclusion constraint" in err_str or "no_overlapping_bookings" in err_str:
        return format_error_response(
            code="ROOM_UNAVAILABLE",
            message="The room is not available for the requested dates.",
            status_code=status.HTTP_409_CONFLICT
        )

    # 2. SQLSTATE 23505: Unique Violation
    if pgcode == "23505" or "unique constraint" in err_str:
        if "one_review_per_booking" in err_str or "review_booking_id_key" in err_str:
            return format_error_response(
                code="DUPLICATE_REVIEW",
                message="A review has already been submitted for this stay.",
                status_code=status.HTTP_409_CONFLICT
            )
        if "guest_email_key" in err_str or "account_email" in err_str or "unique_guest_email" in err_str:
            return format_error_response(
                code="EMAIL_EXISTS",
                message="An account with this email address already exists.",
                status_code=status.HTTP_409_CONFLICT
            )
        if "room_property_id_room_number_key" in err_str:
            return format_error_response(
                code="DUPLICATE_ROOM",
                message="A room with this number already exists for this property.",
                status_code=status.HTTP_409_CONFLICT
            )
        return format_error_response(
            code="RESOURCE_CONFLICT",
            message="The submitted data conflicts with an existing record.",
            status_code=status.HTTP_409_CONFLICT
        )

    # 3. SQLSTATE P0001: Trigger / User-defined Exception (Capacity trigger)
    if pgcode == "P0001" or "check_guest_capacity" in err_str or "exceeds maximum occupancy" in err_str:
        return format_error_response(
            code="EXCEEDS_OCCUPANCY",
            message="Guest count exceeds the maximum allowed occupancy for this room type.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
        )

    # 4. SQLSTATE 23514: Check Constraint Violation
    if pgcode == "23514" or "check constraint" in err_str:
        if "stars" in err_str:
            msg = "Property stars rating must be between 1 and 5."
        elif "rating" in err_str:
            msg = "Review rating must be an integer between 1 and 5."
        elif "guest_count" in err_str:
            msg = "Guest count must be greater than zero."
        elif "max_occupancy" in err_str:
            msg = "Maximum occupancy must be greater than zero."
        elif "check_role_property_scope" in err_str:
            msg = "Staff and managers must be assigned to a property; guests and owners must not."
        else:
            msg = "The submitted data violates database domain constraints."
        return format_error_response(
            code="INVALID_FIELD_VALUE",
            message=msg,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
        )

    # 5. SQLSTATE 23503: Foreign Key Violation
    if pgcode == "23503" or "foreign key constraint" in err_str:
        return format_error_response(
            code="RESOURCE_NOT_FOUND",
            message="Referenced parent resource does not exist.",
            status_code=status.HTTP_404_NOT_FOUND
        )

    # 6. SQLSTATE 23502: Not Null Violation
    if pgcode == "23502" or "not-null constraint" in err_str:
        return format_error_response(
            code="MISSING_REQUIRED_FIELD",
            message="A required field was missing from the request.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
        )

    # Fallback safe error
    return format_error_response(
        code="DATABASE_ERROR",
        message="A database operation failed while processing your request.",
        status_code=status.HTTP_400_BAD_REQUEST
    )
