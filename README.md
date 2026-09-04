# Kaveri Stays API

Production-grade hotel booking REST API for **Kaveri Stays** — a 3-property chain in Coorg, Ooty, and Alleppey.

Built with **FastAPI + PostgreSQL** and featuring JWT-based RBAC, database constraint enforcement, seasonal rate pricing, and comprehensive test coverage.

---

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 18 running locally (`kaveri` database already exists)
- Git

### Setup

```bash
# 1. Clone / navigate to project
cd "c:\kaveri project"

# 2. Create virtual environment
python -m venv venv
.\venv\Scripts\activate      # Windows
# source venv/bin/activate   # Linux/Mac

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
copy .env.example .env
# Edit .env and set a strong SECRET_KEY (min 32 chars)

# 5. Start the API server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Access

| URL | Description |
|-----|-------------|
| http://localhost:8000/docs | **Swagger UI** (interactive) |
| http://localhost:8000/redoc | ReDoc documentation |
| http://localhost:8000/openapi.json | Raw OpenAPI 3.1 JSON |
| http://localhost:8000/health | Health check |

---

## Project Structure

```
kaveri project/
├── app/
│   ├── main.py              # FastAPI app, CORS, exception handlers, router mounts
│   ├── config.py            # Environment settings (fails loudly on missing SECRET_KEY)
│   ├── database.py          # SQLAlchemy engine, session factory, get_db()
│   ├── security.py          # bcrypt hashing, JWT encode/decode, token utils
│   ├── exceptions.py        # Central SQLSTATE → HTTP exception handler
│   ├── dependencies.py      # get_current_user, require_role, enforce_property_scope
│   ├── models/
│   │   └── __init__.py      # SQLAlchemy ORM models (all 10 tables)
│   ├── schemas/
│   │   └── __init__.py      # Pydantic v2 request/response models
│   ├── routers/
│   │   ├── auth.py          # /auth/* — register, login, refresh, logout, me
│   │   ├── hotels.py        # /properties/* — list and detail
│   │   ├── rooms.py         # /rooms/availability — GiST exclusion-based search
│   │   ├── bookings.py      # /bookings/* — full CRUD + state machine
│   │   ├── payments.py      # /bookings/{id}/payments — payment recording
│   │   ├── reviews.py       # /bookings/{id}/review — post-stay reviews
│   │   └── reports.py       # /reports/* — occupancy, ADR, RevPAR
│   └── services/
│       ├── booking_service.py   # Day-by-day rate calculation, atomic booking creation
│       ├── payment_service.py   # Idempotency-key deduplication, overpayment guard
│       └── report_service.py    # SQL-computed Occupancy, ADR, RevPAR
├── tests/
│   ├── test_auth.py             # Register, login, token rotation, logout
│   ├── test_bookings.py         # Properties, availability, bookings, state machine, reports
│   ├── test_constraints.py      # All 6 PostgreSQL SQLSTATE → HTTP mappings
│   ├── test_authorization.py    # Full 4-role × 19-endpoint access matrix
│   └── test_security.py         # JWT attacks, SQL injection, mass assignment, timing
├── 01_constraints.md        # Stage 1: Constraint inventory and SQLSTATE mapping
├── 02_auth_schema.sql       # Stage 2: Auth DDL — account, refresh_token tables + seed
├── 02_auth_design.md        # Stage 2: Auth architecture design
├── 03_openapi_original.yaml # Stage 3: Hand-authored OpenAPI 3.1 spec
├── 03_authorization_matrix.md
├── 04_reconciliation.md     # Stage 4/5 reconciliation report
├── 05_openapi_final.yaml    # Authoritative final API spec
├── 06_spec_drift.md         # Stage 6: Swagger drift analysis
├── 06_postman_collection.json
├── 06_postman_environments/ # guest / staff / manager / owner .json
├── 07_authorization_matrix.md  # Stage 7: Full role matrix with test results
├── 08_break_it.md           # Stage 8: 20 security attack analyses
├── 09_performance.md        # Stage 9: N+1 analysis, EXPLAIN ANALYZE, pool config
├── requirements.txt
├── .env.example
└── pytest.ini
```

---

## Test Accounts (seeded by `02_auth_schema.sql`)

| Role | Email | Password |
|------|-------|----------|
| owner | owner@kaveristays.com | Password123! |
| manager (Coorg) | manager.coorg@kaveristays.com | Password123! |
| manager (Ooty) | manager.ooty@kaveristays.com | Password123! |
| manager (Alleppey) | manager.alleppey@kaveristays.com | Password123! |
| staff (Coorg) | staff.coorg@kaveristays.com | Password123! |
| staff (Ooty) | staff.ooty@kaveristays.com | Password123! |
| staff (Alleppey) | staff.alleppey@kaveristays.com | Password123! |
| guest | aarav.sharma@example.com | Password123! |
| guest | anita.desai@example.com | Password123! |
| guest | guest@example.com | Password123! |

---

## Running Tests

```bash
# All tests with coverage report
python -m pytest tests/ -v --cov=app --cov-report=term-missing

# Specific test files
python -m pytest tests/test_auth.py -v
python -m pytest tests/test_security.py -v
python -m pytest tests/test_authorization.py -v

# All 82 tests in ~10 seconds
```

---

## API Overview

### Authentication Flow
```
POST /auth/register    → 201 AccountResponse
POST /auth/login       → 200 TokenResponse (access_token + refresh_token)
GET  /auth/me          → 200 AccountResponse
POST /auth/refresh     → 200 TokenResponse (rotated tokens)
POST /auth/logout      → 200 MessageResponse (revokes refresh token)
```

### Public Endpoints (no auth required)
```
GET  /properties               → List all 3 properties
GET  /properties/{id}          → Property detail + room types
GET  /rooms/availability       → Available rooms for dates (incl. rates)
```

### Booking Lifecycle
```
POST /bookings                 → Create booking + deposit (guest/staff/manager/owner)
GET  /bookings                 → List bookings (scoped by role)
GET  /bookings/{id}            → Booking detail
POST /bookings/{id}/check-in   → confirmed → checked_in (staff+)
POST /bookings/{id}/check-out  → checked_in → checked_out (staff+)
POST /bookings/{id}/cancel     → confirmed → cancelled (guest own, manager prop, owner all)
```

### Payments & Reviews
```
GET  /bookings/{id}/payments   → List payments
POST /bookings/{id}/payments   → Record payment (supports Idempotency-Key header)
POST /bookings/{id}/review     → Submit review (checked_out only, 1 per booking)
```

### Reports (manager/owner only)
```
GET  /reports/occupancy        → Occupancy % by property and date range
GET  /reports/revenue          → Total revenue, ADR, RevPAR by property
```

---

## Security Model

| Mechanism | Implementation |
|-----------|----------------|
| Authentication | JWT HS256 access tokens (15 min TTL) |
| Refresh | SHA-256 hashed refresh tokens (7 day TTL) with rotation |
| Token reuse | Revokes all account tokens on replay detection |
| Password storage | bcrypt cost factor 12 |
| Role-based access | 4 roles: guest / staff / manager / owner |
| Property scoping | Manager and staff cannot cross property boundaries |
| Guest privacy | Returns 404 (not 403) for cross-guest booking access |
| DB exception isolation | All PostgreSQL errors translated via central handler |
| SQL injection | All queries use SQLAlchemy parameterised text() |
| Sort injection | sort_by validated against explicit whitelist |

---

## Database Design (existing, not modified)

The PostgreSQL `kaveri` database contains:

- `property` — 3 properties (Coorg, Ooty, Alleppey)
- `room_type` — Standard (max 2), Deluxe (max 3), Suite (max 4)
- `room` — 21 rooms across 3 properties
- `rate` — Seasonal pricing with GiST exclusion constraint `no_overlapping_rates`
- `booking` — With GiST exclusion constraint `no_overlapping_bookings` + capacity trigger
- `payment`, `review`, `guest`
- `account`, `refresh_token` — Added by Stage 2 migration

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | ✅ | PostgreSQL connection string |
| `SECRET_KEY` | ✅ | JWT signing key (min 32 chars) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Optional | Default: 15 |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Optional | Default: 7 |
| `ALGORITHM` | Optional | Default: HS256 |
| `ENVIRONMENT` | Optional | Default: development |
