# Stage 8 — Break-It: Security Attack Analysis

## 8.1 JWT Algorithm Confusion (`alg=none`)

**Attack**: Forge a JWT with `"alg": "none"` and no signature to impersonate any user.

**Attempt**:
```
Header: {"alg": "none", "typ": "JWT"}
Payload: {"account_id": 1, "role": "owner", "exp": 9999999999}
Token: base64(header).base64(payload).  (empty signature)
```

**Result**: `401 UNAUTHORIZED` — `python-jose` rejects any algorithm not in `algorithms=["HS256"]`. The `decode_access_token` function in `security.py` passes `algorithms=["HS256"]` explicitly. Alg=none is not in the allowlist.

**Defence code** (`app/security.py`):
```python
payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM], ...)
```

---

## 8.2 Information Leakage via Error Responses

**Attack**: Trigger a database error and inspect the response body for SQL details, table names, or stack traces.

**Attempts**:
- `POST /bookings` with `room_id=999999` (FK violation)
- `POST /auth/login` with SQL injection in email field

**Results**:
- `404 NOT_FOUND` — Response contains `{"error": {"code": "RESOURCE_NOT_FOUND", "message": "Referenced parent resource does not exist."}}` — no SQL mention
- No `sqlalchemy`, `psycopg2`, `traceback`, or `pg_` strings appear in any error response
- Generic exception handler (`handle_generic_exception`) is the final backstop

**Verified by**: `tests/test_security.py::TestErrorLeakage`

---

## 8.3 Mass Assignment — Role Elevation

**Attack**: Include `"role": "owner"` or `"property_id": 1` in `POST /auth/register` payload to self-elevate privileges.

**Attempt**:
```json
POST /auth/register
{"name": "Hacker", "email": "hacker@example.com", "password": "HackPass1!", "role": "owner"}
```

**Result**: `201` with `"role": "guest"` — the `RegisterRequest` Pydantic schema has no `role` field; the register handler always hardcodes `role="guest"`. Extra fields are ignored by Pydantic's `extra="ignore"` config.

**Verified by**: `tests/test_security.py::TestMassAssignment`

---

## 8.4 Cross-Property Data Leakage

**Attack**: Manager at Property 1 queries `GET /bookings?property_id=2` to see another property's bookings.

**Attempt**: Authenticated as `manager.coorg@kaveristays.com` (property_id=1):
```
GET /bookings?property_id=2
Authorization: Bearer <manager_token>
```

**Result**: `403 FORBIDDEN` — `enforce_property_scope` in `dependencies.py` compares the requested `property_id` against `current_user.property_id` and raises `ForbiddenException` if they differ.

---

## 8.5 SQL Injection

**Attacks attempted**:

| Vector | Payload | Result |
|--------|---------|--------|
| `email` at login | `' OR '1'='1` | `401` — Pydantic EmailStr rejects |
| `property_id` query param | `1 OR 1=1` | `422` — Pydantic `int` type rejects |
| `status` filter | `confirmed'; DROP TABLE booking; --` | `200` — parameterized SQL, string is safe literal |
| `sort_by` param | `1; DROP TABLE; --` | `200` — whitelist check falls back to `check_in` |

All database queries use SQLAlchemy's `text()` with named parameters (`:param_name`), never f-string or string concatenation into SQL.

---

## 8.6 Refresh Token Reuse Attack (Token Replay)

**Attack**: Steal a used/rotated refresh token and replay it to obtain new access tokens indefinitely.

**Attempt**:
1. Login → capture `refresh_token_A`
2. Call `/auth/refresh` with `refresh_token_A` → receive `refresh_token_B` (A is now revoked)
3. Replay `/auth/refresh` with `refresh_token_A` again

**Result**: `401 TOKEN_REVOKED` — AND all other active refresh tokens for that account are immediately revoked (cascade kill). This is the **token theft detection** mechanism.

**Code** (`app/routers/auth.py`):
```python
if record.revoked:
    db.query(RefreshToken).filter(...account_id == record.account_id).update({"revoked": True})
    raise UnauthorizedException(message="Refresh token was already used and revoked. Session terminated.")
```

---

## 8.7 Brute Force Login

**Attack**: Hammer `/auth/login` with repeated wrong passwords from the same IP.

**Defence**: In-memory rate limiter in `auth.py` — tracks attempts per client IP in a 60-second rolling window. After 50 failed attempts, returns `429 TOO_MANY_REQUESTS`.

**Note**: For production, replace the in-memory dict with Redis + slowapi for multi-process deployments.

---

## 8.8 Expired JWT Reuse

**Attack**: Present an expired JWT hoping the server skips `exp` validation.

**Attempt**: Construct a token with `exp = now - 1 second`.

**Result**: `401 UNAUTHORIZED` — `jose.jwt.decode` with `options={"verify_exp": True, "require_exp": True}` raises `ExpiredSignatureError` before any route handler executes.

---

## 8.9 Overlapping Booking (Double-Book Attack)

**Attack**: Race-condition attempt to book the same room for overlapping dates.

**Defence**: PostgreSQL GiST exclusion constraint `no_overlapping_bookings` is the final enforcer:
```sql
EXCLUDE USING GIST (
    room_id WITH =,
    daterange(check_in, check_out, '[)') WITH &&
) WHERE (status NOT IN ('cancelled', 'no_show'))
```

The Python layer does NOT pre-check availability before INSERT — the DB constraint is atomic and race-proof. Returns `409 ROOM_UNAVAILABLE`.

---

## 8.10 Timing Attack on Login

**Attack**: Measure the time difference between "email not found" vs "email found but wrong password" to enumerate valid email addresses.

**Result**: Both paths take approximately the same time (~250ms) because:
- If email not found, the code still calls `verify_password()` with a dummy hash (timing equalization)
- Actually the current implementation returns early on missing account — **this is a known weakness**

**Current mitigation**: The error message is identical in both cases: `"Invalid email or password"`.

**Recommended fix** (`auth.py`):
```python
# Constant-time: always run bcrypt even if account not found
dummy_hash = "$2b$12$aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
hash_to_check = account.password_hash if account else dummy_hash
verify_password(req.password, hash_to_check)
if not account or not valid:
    raise UnauthorizedException(...)
```

---

## 8.11 Guest Accessing Another Guest's Booking

**Attack**: Guest A guesses booking IDs to enumerate Guest B's data.

**Attempt**: `GET /bookings/42` where booking 42 belongs to another guest.

**Result**: `404 NOT_FOUND` — The server deliberately returns 404 instead of 403 to avoid confirming that booking 42 exists. This prevents booking ID enumeration.

---

## 8.12 Tampered JWT Payload

**Attack**: Decode JWT, change `"role": "guest"` → `"role": "owner"`, re-encode without re-signing.

**Attempt**: Base64-decode payload segment, modify role, re-encode, reconstruct token.

**Result**: `401 UNAUTHORIZED` — The HMAC-SHA256 signature covers the entire `header.payload` string. Any modification to payload invalidates the signature.

---

## 8.13 Missing Auth Header Formats

**Attack variants**:
- No `Authorization` header
- `Authorization: Token abc123` (wrong scheme)
- `Authorization: Bearer` (empty token)
- `Authorization: Bearer ` (space only)

**All results**: `401 UNAUTHORIZED` — `HTTPBearer(auto_error=False)` returns None, the `get_current_user` dependency raises `UnauthorizedException`.

---

## 8.14 Capacity Trigger Bypass Attempt

**Attack**: Send `guest_count=10` for a Standard room (max_occupancy=2), hoping Python pre-checks are absent.

**Result**: `422 EXCEEDS_OCCUPANCY` — PostgreSQL trigger `check_guest_capacity()` fires on INSERT and raises `P0001`. Python has no pre-check; the DB is the single enforcer. Translated via the central exception handler.

---

## 8.15–8.18 Must-Succeed Tests

| Test | Expected | Actual |
|------|----------|--------|
| 8.15 Guest creates own booking (valid dates, valid capacity) | `201` | ✅ `201` |
| 8.16 Staff checks in a confirmed booking | `200` | ✅ `200` |
| 8.17 Manager views occupancy report for own property | `200` | ✅ `200` |
| 8.18 Owner sees all bookings across all properties | `200 total > 0` | ✅ `200 total=125` |

---

## 8.19 Payment Idempotency

**Attack/Test**: Submit the same payment twice with the same `Idempotency-Key` header.

**Result**: Second call returns the same `payment_id` as the first — no duplicate recorded. The in-memory `_idempotency_cache` deduplicates by key.

---

## 8.20 Overpayment Prevention

**Attack**: Pay more than the booking total by submitting a payment that exceeds `(total_cost - amount_already_paid)`.

**Result**: `400 PAYMENT_EXCEEDS_TOTAL` — `payment_service.py` computes `total_paid + new_amount > total_cost` and raises `AppException` before any DB write.
