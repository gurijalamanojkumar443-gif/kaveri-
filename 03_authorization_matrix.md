 # Stage 3 — API Design & Authorization Matrix

## 3.1 & 3.11 Full Authorization Matrix

Every cell in this matrix explicitly denotes `ALLOWED` or `DENIED` with operational scope rules.

| Endpoint | Method | Guest | Staff | Manager | Owner | Scope & Governance Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `/auth/register` | `POST` | **ALLOWED** | **DENIED** | **DENIED** | **DENIED** | Public self-service registration (creates `guest` role only). |
| `/auth/login` | `POST` | **ALLOWED** | **ALLOWED** | **ALLOWED** | **ALLOWED** | Rate-limited credentials authentication. |
| `/auth/refresh` | `POST` | **ALLOWED** | **ALLOWED** | **ALLOWED** | **ALLOWED** | Refresh token rotation. |
| `/auth/logout` | `POST` | **ALLOWED** | **ALLOWED** | **ALLOWED** | **ALLOWED** | Refresh token revocation. |
| `/me` | `GET` | **ALLOWED** | **ALLOWED** | **ALLOWED** | **ALLOWED** | Returns caller profile details. |
| `/properties` | `GET` | **ALLOWED** | **ALLOWED** | **ALLOWED** | **ALLOWED** | Public property catalog. |
| `/properties/{id}` | `GET` | **ALLOWED** | **ALLOWED** | **ALLOWED** | **ALLOWED** | Public property room types and details. |
| `/rooms/availability` | `GET` | **ALLOWED** | **ALLOWED** | **ALLOWED** | **ALLOWED** | Public room availability with rate calculation. |
| `/bookings` | `GET` | **ALLOWED** | **ALLOWED** | **ALLOWED** | **ALLOWED** | Scoped: Guest sees own; Staff/Manager sees assigned property; Owner sees all. |
| `/bookings` | `POST` | **ALLOWED** | **ALLOWED** | **ALLOWED** | **ALLOWED** | Atomic creation + deposit transaction. |
| `/bookings/{id}` | `GET` | **ALLOWED** | **ALLOWED** | **ALLOWED** | **ALLOWED** | Scoped: Guest sees own only (returns 404 on other guests to prevent enumeration); Staff/Manager sees assigned property; Owner sees all. |
| `/bookings/{id}/check-in` | `POST` | **DENIED** | **ALLOWED** | **ALLOWED** | **ALLOWED** | Front desk operation; guest cannot self-check-in. |
| `/bookings/{id}/check-out` | `POST` | **DENIED** | **ALLOWED** | **ALLOWED** | **ALLOWED** | Front desk operation; guest cannot self-check-out. |
| `/bookings/{id}/cancel` | `POST` | **ALLOWED** | **DENIED** | **ALLOWED** | **ALLOWED** | Guest can cancel own confirmed booking; Manager cancels for own property; Owner cancels any. |
| `/bookings/{id}/payments` | `GET` | **ALLOWED** | **ALLOWED** | **ALLOWED** | **ALLOWED** | Guest sees payments for own booking; Staff/Manager/Owner see property payments. |
| `/bookings/{id}/payments` | `POST` | **ALLOWED** | **ALLOWED** | **ALLOWED** | **ALLOWED** | Records deposit or balance payments; supports Idempotency keys. |
| `/bookings/{id}/review` | `POST` | **ALLOWED** | **DENIED** | **DENIED** | **DENIED** | Guest who completed stay (`checked_out`) can post exactly 1 review. |
| `/reports/occupancy` | `GET` | **DENIED** | **DENIED** | **ALLOWED** | **ALLOWED** | Manager views own property occupancy; Owner views any/all properties. |
| `/reports/revenue` | `GET` | **DENIED** | **DENIED** | **ALLOWED** | **ALLOWED** | ADR & RevPAR financial metrics: Manager sees own property; Owner sees all. |

---

## 3.2 Availability Design & Date Boundary Rule

The endpoint `/rooms/availability` accepts `property_id`, `check_in`, `check_out`, and optional `room_type_id`.
- **Date Boundary Handling**:
  The exclusion range in PostgreSQL is defined with half-open intervals `[check_in, check_out)`.
  If Guest A checks out on the 15th (`[2026-06-10, 2026-06-15)`), the 15th is an open upper bound and is NOT occupied.
  When Guest B requests availability starting on the 15th (`[2026-06-15, 2026-06-20)`), PostgreSQL GiST range overlap operator `&&` evaluates to `FALSE`. The room is returned as available.

---

## 3.3 Booking Lifecycle Design: Action Endpoints vs Generic PATCH

**Decision**: Separate explicit action endpoints:
- `POST /bookings/{id}/check-in`
- `POST /bookings/{id}/check-out`
- `POST /bookings/{id}/cancel`

### Defense:
1. **Explicit Semantic Intent**: State transitions in hotel management carry distinct business side-effects (e.g. check-in verifies arrival, check-out triggers review eligibility, cancellation releases exclusion locks).
2. **Granular Authorization**: `PATCH /bookings/{id}` with `{"status": "checked_in"}` makes route-level role authorization difficult because a single endpoint must dynamically inspect which JSON field is being modified. Dedicated action endpoints allow declarative, dependency-injected security decorators (`@router.post("/check-in", dependencies=[Depends(require_staff)])`).

---

## 3.4 Payment Design & Idempotency Key

- Endpoint: `POST /bookings/{id}/payments`
- Header: `Idempotency-Key: <unique_client_generated_key>`
- **Behavior**:
  - Multiple instalment payments are supported against a single booking.
  - When an idempotency key is submitted, the server records the key with the payment transaction.
  - If a mobile app or tablet loses Wi-Fi connection and retries the exact same payment request, the database unique constraint or idempotency cache intercepts the duplicate key and returns the original `201` payment record without charging a second time.

---

## 3.5 Reporting URL Structure

**Decision**: `/reports/occupancy` and `/reports/revenue` (with `property_id` query parameter).

### Defense:
Global cross-property reports (comparing Coorg, Ooty, and Alleppey) cannot cleanly fit under a `/properties/{id}/reports` path. A unified `/reports/...` namespace allows the `owner` to query across all properties simultaneously or filter by a specific property, while `manager` requests are automatically scoped to their designated `account.property_id`.

---

## 3.6 Pagination Strategy

**Decision**: Standard `limit` (max 100, default 20) and `offset` (default 0) query parameters.
- Response Envelope:
  ```json
  {
    "total": 124,
    "limit": 20,
    "offset": 0,
    "items": [...]
  }
  ```
- **Page 400 Behavior**: Negative `offset` or `limit <= 0` or `limit > 100` returns `422 Unprocessable Entity` via Pydantic query validation. If `offset >= total`, the endpoint returns `200 OK` with `"items": []`.

---

## 3.7 Empty List Rule

**Standard Applied Everywhere**: `200 OK` with an empty array `[]` (or `{"total": 0, "items": []}`).
An empty collection is a valid result set representing zero matching records, not a missing route or missing resource (which would be `404`).

---

## 3.8 Strict Separation: 401 Unauthorized vs 403 Forbidden

- **`401 Unauthorized`**: Authentication is missing, token is malformed, expired, forged, or secret signature is invalid.
- **`403 Forbidden`**: The caller is authenticated and their identity is verified, but their role or property assignment does not have permission to execute this operation (e.g. a guest attempting check-in, or an Ooty manager requesting Coorg financial revenue).

---

## 3.9 Standard Date Format: `YYYY-MM-DD`

- All hotel stay dates are represented as ISO 8601 calendar dates: `YYYY-MM-DD` (e.g., `2026-06-01`).
- **Why Dates rather than Timestamps**: Hotel nights are discrete calendar date entities bound by hotel check-in/check-out policies (e.g. 2:00 PM check-in, 11:00 AM check-out). Timestamps introduce timezone conversion bugs across clients and daylight saving distortions.

---

## 3.10 Unified Error Envelope

All API errors (validation, authorization, constraint violations, not found, conflicts) follow one consistent shape:

```json
{
  "error": {
    "code": "ROOM_UNAVAILABLE",
    "message": "The room is not available for the requested dates.",
    "details": []
  }
}
```

---

## 3.12 Deliberately Omitted Endpoints

1. **`DELETE /bookings/{id}` (Hard Delete)**:
   - Permanently deleting bookings would destroy financial audit trails, historical occupancy statistics, tax reconciliation, and cascade-corrupt historical payment records. The legal business mechanism for removing a booking is `POST /bookings/{id}/cancel`.
2. **Client-Supplied Nightly Rate in `POST /bookings`**:
   - The client MUST NOT supply the authoritative nightly rate. The server calculates rates strictly from the `rate` table.
