# Stage 6 — Swagger UI and Postman Collection

## 6.1 Live Swagger UI

With the server running (`uvicorn app.main:app --reload`), visit:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Raw OpenAPI JSON**: http://localhost:8000/openapi.json

FastAPI auto-generates the OpenAPI 3.1 specification from the route definitions, Pydantic models, and docstrings. The server at `/openapi.json` is the authoritative live spec.

## 6.2 Spec Drift Analysis

Comparing `05_openapi_final.yaml` (hand-authored) against the live `/openapi.json` (auto-generated):

| Section | Planned | Actual | Status |
|---------|---------|--------|--------|
| `POST /auth/register` | 201 AccountResponse | 201 AccountResponse | ✅ Match |
| `POST /auth/login` | 200 TokenResponse | 200 TokenResponse | ✅ Match |
| `POST /auth/refresh` | 200 TokenResponse | 200 TokenResponse | ✅ Match |
| `POST /auth/logout` | 200 MessageResponse | 200 MessageResponse | ✅ Match |
| `GET /auth/me` | 200 AccountResponse | 200 AccountResponse | ✅ Match |
| `GET /properties` | 200 List[Property] | 200 List[Property] | ✅ Match |
| `GET /properties/{id}` | 200 PropertyDetail | 200 PropertyDetail | ✅ Match |
| `GET /rooms/availability` | 200 List[Room] + rates | 200 List[Room] + rates | ✅ Match |
| `GET /bookings` | 200 Paginated | 200 Paginated | ✅ Match |
| `POST /bookings` | 201 BookingDetail | 201 BookingDetail | ✅ Match |
| `GET /bookings/{id}` | 200 BookingDetail | 200 BookingDetail | ✅ Match |
| `POST /bookings/{id}/check-in` | 200 BookingDetail | 200 BookingDetail | ✅ Match |
| `POST /bookings/{id}/check-out` | 200 BookingDetail | 200 BookingDetail | ✅ Match |
| `POST /bookings/{id}/cancel` | 200 BookingDetail | 200 BookingDetail | ✅ Match |
| `GET /bookings/{id}/payments` | 200 List[Payment] | 200 List[Payment] | ✅ Match |
| `POST /bookings/{id}/payments` | 201 Payment | 201 Payment | ✅ Match |
| `POST /bookings/{id}/review` | 201 Review | 201 Review | ✅ Match |
| `GET /reports/occupancy` | 200 OccupancyReport | 200 OccupancyReport | ✅ Match |
| `GET /reports/revenue` | 200 RevenueReport | 200 RevenueReport | ✅ Match |

**Result: Zero spec drift detected.** All 19 endpoints match the final specification.

### Minor Notes
- `HTTP_422_UNPROCESSABLE_ENTITY` constant renamed to `HTTP_422_UNPROCESSABLE_CONTENT` in newer Starlette — non-functional, status code integer `422` is identical. Will be updated.
- Error body shape `{"error": {"code": "...", "message": "...", "details": [...]}}` is consistent across all 6 error categories.

## 6.3 Postman Environments

Four environments are provided in `06_postman_environments/`:

### `guest.json` — Guest Environment
```
base_url: http://localhost:8000
email: aarav.sharma@example.com
password: Password123!
access_token: (updated after /auth/login)
refresh_token: (updated after /auth/login)
```

### `staff.json` — Staff Environment
```
base_url: http://localhost:8000
email: staff.coorg@kaveristays.com
password: Password123!
property_id: 1
access_token: (updated after /auth/login)
```

### `manager.json` — Manager Environment
```
base_url: http://localhost:8000
email: manager.coorg@kaveristays.com
password: Password123!
property_id: 1
access_token: (updated after /auth/login)
```

### `owner.json` — Owner Environment
```
base_url: http://localhost:8000
email: owner@kaveristays.com
password: Password123!
access_token: (updated after /auth/login)
```

## 6.4 Postman Collection

The `06_postman_collection.json` collection contains all 19 endpoints with:
- Pre-request scripts that call `/auth/login` and capture `access_token` into the environment variable
- Test scripts that assert `pm.response.to.have.status()` for expected codes
- Example request/response bodies for all endpoints
