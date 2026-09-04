from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError, DataError, InternalError, OperationalError

from app.config import settings
from app.exceptions import AppException, handle_app_exception, handle_database_exception
from app.routers.auth import router as auth_router
from app.routers.hotels import router as hotels_router
from app.routers.rooms import router as rooms_router
from app.routers.bookings import router as bookings_router
from app.routers.payments import router as payments_router
from app.routers.reviews import router as reviews_router
from app.routers.reports import router as reports_router
from app.routers.agent import router as agent_router

app = FastAPI(
    title="Kaveri Stays API",
    description=(
        "Production-grade hotel booking API for Kaveri Stays — a 3-property chain "
        "in Coorg, Ooty, and Alleppey. Provides complete guest registration, room availability, "
        "bookings, payments, reviews, management reporting, and Kaveri AI Concierge Agent with JWT-based RBAC."
    ),
    version="1.0.0",
    contact={
        "name": "Kaveri Stays Engineering",
        "email": "api@kaveristays.in"
    },
    license_info={
        "name": "Proprietary"
    },
    openapi_tags=[
        {"name": "Authentication", "description": "Register, login, refresh, logout, and profile."},
        {"name": "AI Agent", "description": "Kaveri AI Concierge — natural language queries, tool execution, and booking actions."},
        {"name": "Properties", "description": "List and inspect hotel properties."},
        {"name": "Rooms", "description": "Room availability search with date-range exclusion logic."},
        {"name": "Bookings", "description": "Full booking lifecycle — create, check-in, check-out, cancel."},
        {"name": "Payments", "description": "Record and retrieve payments against bookings."},
        {"name": "Reviews", "description": "Post-stay reviews (checked_out bookings only)."},
        {"name": "Reports", "description": "Occupancy, ADR, and RevPAR reports (manager/owner only)."}
    ]
)

# ─── CORS ───────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"]
)

# ─── Exception Handlers ─────────────────────────────────────────────────────

@app.exception_handler(AppException)
def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return handle_app_exception(request, exc)

@app.exception_handler(IntegrityError)
def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    return handle_database_exception(request, exc)

@app.exception_handler(DataError)
def data_error_handler(request: Request, exc: DataError) -> JSONResponse:
    return handle_database_exception(request, exc)

@app.exception_handler(InternalError)
def internal_error_handler(request: Request, exc: InternalError) -> JSONResponse:
    return handle_database_exception(request, exc)

@app.exception_handler(OperationalError)
def operational_error_handler(request: Request, exc: OperationalError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "error": {
                "code": "DATABASE_UNAVAILABLE",
                "message": "Cannot connect to the database. Please retry shortly.",
                "details": []
            }
        }
    )

@app.exception_handler(RequestValidationError)
def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = []
    for err in exc.errors():
        details.append({
            "loc": list(err.get("loc", [])),
            "msg": err.get("msg", ""),
            "type": err.get("type", "")
        })
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request payload failed validation.",
                "details": details
            }
        }
    )

@app.exception_handler(Exception)
def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Last-resort handler — never leak stack traces in production
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected server error occurred.",
                "details": []
            }
        }
    )

# ─── Routers ────────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(hotels_router)
app.include_router(rooms_router)
app.include_router(bookings_router)
app.include_router(payments_router)
app.include_router(reviews_router)
app.include_router(reports_router)
app.include_router(agent_router)

# ─── Health Check ───────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"], summary="API health check", include_in_schema=True)
def health_check():
    return {"status": "ok", "service": "kaveri-stays-api", "version": "1.0.0"}

@app.get("/", tags=["Health"], include_in_schema=False)
def root():
    return {"message": "Kaveri Stays API is running. Visit /docs for Swagger UI."}
