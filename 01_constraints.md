# Stage 1 — Constraint Inventory & Failure Mapping

## 1.1 Constraint Inventory

This inventory represents every constraint present in the active PostgreSQL database (`kaveri`). Every SQLSTATE was captured by deliberately triggering the constraint inside a rollbacked transaction.

| Table | Constraint Name | Type | Business Rule Enforced | PostgreSQL SQLSTATE |
| :--- | :--- | :--- | :--- | :--- |
| `property` | `property_pkey` | PRIMARY KEY | Property ID must be unique and non-null | `23505` |
| `property` | `property_name_not_null` | NOT NULL | Property name is mandatory | `23502` |
| `property` | `property_city_not_null` | NOT NULL | Property city location is mandatory | `23502` |
| `property` | `property_stars_check` | CHECK | Hotel star rating must be between 1 and 5 | `23514` |
| `room_type` | `room_type_pkey` | PRIMARY KEY | Room type ID must be unique and non-null | `23505` |
| `room_type` | `room_type_type_name_key` | UNIQUE | Room type name (e.g. Standard, Deluxe, Suite) must be unique | `23505` |
| `room_type` | `room_type_type_name_not_null` | NOT NULL | Room type name is mandatory | `23502` |
| `room_type` | `room_type_max_occupancy_check` | CHECK | Maximum occupancy must be greater than 0 | `23514` |
| `room_type` | `room_type_max_occupancy_not_null` | NOT NULL | Maximum occupancy must be specified | `23502` |
| `guest` | `guest_pkey` | PRIMARY KEY | Guest ID must be unique and non-null | `23505` |
| `guest` | `guest_email_key` | UNIQUE | Email address must be unique across all guests | `23505` |
| `guest` | `guest_name_not_null` | NOT NULL | Guest name is mandatory | `23502` |
| `guest` | `guest_email_not_null` | NOT NULL | Guest email is mandatory | `23502` |
| `room` | `room_pkey` | PRIMARY KEY | Room ID must be unique and non-null | `23505` |
| `room` | `room_property_id_fkey` | FOREIGN KEY | Room must belong to an existing property | `23503` |
| `room` | `room_room_type_id_fkey` | FOREIGN KEY | Room must refer to a valid room type | `23503` |
| `room` | `room_property_id_room_number_key` | UNIQUE | Room number must be unique within a given property | `23505` |
| `room` | `room_property_id_not_null` | NOT NULL | Property reference is mandatory | `23502` |
| `room` | `room_room_number_not_null` | NOT NULL | Room number is mandatory | `23502` |
| `room` | `room_room_type_id_not_null` | NOT NULL | Room type reference is mandatory | `23502` |
| `booking` | `booking_pkey` | PRIMARY KEY | Booking ID must be unique and non-null | `23505` |
| `booking` | `booking_guest_id_fkey` | FOREIGN KEY | Booking must be associated with an existing guest | `23503` |
| `booking` | `booking_room_id_fkey` | FOREIGN KEY | Booking must be associated with an existing room | `23503` |
| `booking` | `booking_guest_count_check` | CHECK | Guest count must be greater than 0 | `23514` |
| `booking` | `booking_guest_id_not_null` | NOT NULL | Guest reference is mandatory | `23502` |
| `booking` | `booking_room_id_not_null` | NOT NULL | Room reference is mandatory | `23502` |
| `booking` | `booking_check_in_not_null` | NOT NULL | Check-in date is mandatory | `23502` |
| `booking` | `booking_check_out_not_null` | NOT NULL | Check-out date is mandatory | `23502` |
| `booking` | `booking_guest_count_not_null` | NOT NULL | Guest count is mandatory | `23502` |
| `booking` | `booking_status_not_null` | NOT NULL | Booking status is mandatory | `23502` |
| `booking` | `no_overlapping_bookings` | EXCLUDE (GiST) | No overlapping date ranges for the same physical room (excluding cancelled/no_show) | `23P01` |
| `booking` | `enforce_guest_capacity` (Trigger) | TRIGGER (PL/pgSQL) | Guest count must not exceed room type max occupancy | `P0001` |
| `payment` | `payment_pkey` | PRIMARY KEY | Payment ID must be unique and non-null | `23505` |
| `payment` | `payment_booking_id_fkey` | FOREIGN KEY | Payment must refer to an existing booking | `23503` |
| `payment` | `payment_booking_id_not_null` | NOT NULL | Booking reference is mandatory | `23502` |
| `payment` | `payment_amount_not_null` | NOT NULL | Payment amount is mandatory | `23502` |
| `payment` | `payment_method_not_null` | NOT NULL | Payment method is mandatory | `23502` |
| `payment` | `payment_payment_date_not_null` | NOT NULL | Payment date is mandatory | `23502` |
| `review` | `review_pkey` | PRIMARY KEY | Review ID must be unique and non-null | `23505` |
| `review` | `review_booking_id_key` | UNIQUE | Exactly one review per booking stay | `23505` |
| `review` | `review_booking_id_fkey` | FOREIGN KEY | Review must refer to an existing booking | `23503` |
| `review` | `review_rating_check` | CHECK | Review rating must be an integer between 1 and 5 | `23514` |
| `review` | `review_booking_id_not_null` | NOT NULL | Booking reference is mandatory | `23502` |
| `rate` | `rate_pkey` | PRIMARY KEY | Rate ID must be unique and non-null | `23505` |
| `rate` | `rate_property_id_fkey` | FOREIGN KEY | Rate must refer to an existing property | `23503` |
| `rate` | `rate_room_type_id_fkey` | FOREIGN KEY | Rate must refer to an existing room type | `23503` |
| `rate` | `rate_start_date_not_null` | NOT NULL | Rate start date is mandatory | `23502` |
| `rate` | `rate_end_date_not_null` | NOT NULL | Rate end date is mandatory | `23502` |
| `rate` | `rate_nightly_rate_not_null` | NOT NULL | Nightly rate amount is mandatory | `23502` |
| `rate` | `no_overlapping_rates` | EXCLUDE (GiST) | Rate plans for a property + room_type must not have overlapping date ranges | `23P01` |

---

## 1.2 SQLSTATE to HTTP Status Mapping

The API must translate raw database failures into precise, standard HTTP status codes. We employ **5 distinct HTTP status codes** across database and business rule translations:

| SQLSTATE / Error Code | HTTP Status Code | HTTP Status Name | Reason & Translation Rule |
| :--- | :--- | :--- | :--- |
| `23P01` | `409` | Conflict | **Exclusion constraint violation**: Indicates a state conflict with existing database records (e.g., room already booked for requested dates, or overlapping rate periods). |
| `23505` | `409` | Conflict | **Unique constraint violation**: Attempting to register an existing email, post a duplicate review for the same stay, or insert duplicate room numbers. |
| `23503` | `404` / `422` | Not Found / Unprocessable Entity | **Foreign key violation**: If an endpoint refers to a non-existent parent resource in the URL path (e.g. `/bookings/{id}/payments`), it translates to `404 Not Found`. If a payload body references an invalid foreign ID, it translates to `422 Unprocessable Entity`. |
| `23514` | `422` | Unprocessable Entity | **Check constraint violation**: Payload values violate semantic domain invariants (e.g., rating not between 1-5, guest count <= 0, stars not between 1-5). |
| `23502` | `422` | Unprocessable Entity | **Not Null violation**: Missing mandatory field that was not caught at schema parsing. |
| `P0001` | `422` | Unprocessable Entity | **Trigger rule violation**: Business logic enforced by PL/pgSQL trigger (e.g. guest count exceeding room type maximum capacity). |

**Distinct HTTP status codes used:** `400 Bad Request`, `401 Unauthorized`, `403 Forbidden`, `404 Not Found`, `409 Conflict`, and `422 Unprocessable Entity` (6 distinct codes in the HTTP surface, 5 mapped directly from database error states).

---

## 1.3 The Three 409 Conflict Constraints

The three database constraints that can be violated by individually well-formed requests that conflict with existing data are:

1. **`booking.no_overlapping_bookings` (EXCLUDE GiST)**:
   - *Why the request is well-formed*: The request contains a valid `guest_id`, valid `room_id`, syntactically valid `check_in` and `check_out` dates (where `check_out > check_in`), and a positive integer `guest_count`. In isolation, there is nothing malformed about the JSON or the parameters.
   - *Why 400 is wrong*: `400 Bad Request` implies client syntax or structural error. The request syntax is flawless; the failure is caused by state in the database (another active booking already occupies that room on those dates).
   - *Why 409 Conflict is appropriate*: RFC 9110 specifies 409 Conflict when a request cannot be completed due to a conflict with the current state of the target resource.
2. **`review.review_booking_id_key` / `one_review_per_booking` (UNIQUE)**:
   - *Why the request is well-formed*: The review payload has a valid rating (1-5), non-empty comment, and valid authorization header.
   - *Why 400 is wrong*: The submission is valid; the conflict arises because a review has already been submitted for this stay.
   - *Why 409 Conflict is appropriate*: The resource (the single review slot for this booking) has already been created.
3. **`guest.guest_email_key` / `account.email` (UNIQUE)**:
   - *Why the request is well-formed*: The registration body has a well-formed RFC-compliant email address and a strong password meeting all length requirements.
   - *Why 400 is wrong*: The email string is valid; it simply collides with an existing registered identity in the system.
   - *Why 409 Conflict is appropriate*: The email is already claimed in the system state.

---

## 1.4 Booking Exclusion Constraint Capture & Safe Response

### Deliberate Trigger Output from PostgreSQL:
```text
psycopg2.errors.ExclusionViolation: conflicting key value violates exclusion constraint "no_overlapping_bookings"
DETAIL: Key (room_id, daterange(check_in, check_out, '[)'::text))=(1, [2026-06-03,2026-06-07)) conflicts with existing key (room_id, daterange(check_in, check_out, '[)'::text))=(1, [2026-06-01,2026-06-05)).
```

### What Must Not Be Exposed:
1. **Constraint and Table Names**: Do not leak `"no_overlapping_bookings"`, `"booking"`, `"public"`.
2. **Internal Column Names**: Do not expose `room_id`, `daterange`, `check_in`, `check_out`.
3. **Other Guest's Booking Information**: The PostgreSQL error `DETAIL` explicitly prints the exact dates of the conflicting existing booking (`[2026-06-01,2026-06-05)`). Exposing this leaks another guest's travel dates and schedule.
4. **Internal Database Topology**: Leaking SQLSTATE `23P01` or database engine details helps attackers profile backend infrastructure.

### Safe HTTP Response Returned by the API:
**Status Code**: `409 Conflict`
```json
{
  "error": {
    "code": "ROOM_UNAVAILABLE",
    "message": "The room is not available for the requested dates."
  }
}
```

---

## 1.5 Guest Count vs Maximum Occupancy Rule

### Enforcement Mechanism:
The rule is enforced in PostgreSQL by the database trigger:
```sql
CREATE TRIGGER enforce_guest_capacity
BEFORE INSERT OR UPDATE ON booking
FOR EACH ROW EXECUTE FUNCTION check_guest_capacity();
```
The function `check_guest_capacity()` queries `room` joined with `room_type` for the target `room_id` and raises a `P0001` exception if `NEW.guest_count > rt.max_occupancy`:
```text
Guest count (4) exceeds maximum occupancy (3) for room 1
```

### Test Results:
1. **Through PostgreSQL**: Directly executing `INSERT INTO booking (guest_id, room_id, check_in, check_out, guest_count, status) VALUES (1, 1, '2026-05-01', '2026-05-05', 4, 'confirmed');` immediately aborts the transaction with SQLSTATE `P0001`.
2. **Through the API**: Even if Pydantic schema validation on guest count is completely disabled or bypassed, an API `INSERT` cannot bypass this rule because PostgreSQL trigger execution is atomic within the database transaction. The API catches `P0001` and returns `422 Unprocessable Entity` (`{"error": {"code": "EXCEEDS_OCCUPANCY", "message": "Guest count exceeds the maximum allowed occupancy for this room type."}}`).

---

## 1.6 Stage 2.12 Rule: Christmas Spanning / Cross-Period Nightly Rates

### The Rule:
When a booking spans across seasonal rate boundary dates (e.g. from Regular season Dec 20 to Peak Christmas season Dec 28, or Christmas into New Year), the total booking cost cannot be calculated by a single static `nightly_rate` multiplied by total nights. Each night must be priced according to the rate active on that specific calendar date.

### Where it Lives:
- **In the API**: The server-side pricing engine in `app/services/booking_service.py` splits the stay date range night-by-night, looks up the corresponding `nightly_rate` from the `rate` table for each calendar day, and sums the total required deposit and booking balance.
- **What happens if bypassed via psql**: If someone bypasses the API and inserts directly via `psql` into `booking`, the `booking` table only stores `guest_id`, `room_id`, `check_in`, `check_out`, `guest_count`, `status`. PostgreSQL does not store a computed `total_price` column in `booking`. However, the `payment` table records the actual currency received. A direct `psql` inserter could record an underpayment or arbitrary amount unless checked by the application layer.

---

## 1.7 Stage 4 Query Inspection & Risk Profile

Inspecting the 25 Stage 4 database queries reveals critical risk profiles:

1. **Unbounded Result Sets**: Queries like `SELECT * FROM booking` and `SELECT * FROM payment` without `LIMIT` / `OFFSET` pagination will exhaust server memory as the business grows. Whitelisted pagination is mandatory.
2. **Full-Table Scans on Legacy & Unindexed Filters**: Filtering bookings by date range without composite indexes causes sequential scans. We utilize the GiST index `no_overlapping_bookings` and B-tree foreign key indexes.
3. **Cross-Property Leakage (All-Three-Property Queries)**: Queries calculating global occupancy or total revenue across all properties (Coorg, Ooty, Alleppey) must be strictly restricted to the `owner` role. A `manager` must have `WHERE p.property_id = :manager_property_id` injected into the SQL arithmetic.
4. **Sensitive Information Exposure**: Joining `guest` with `payment` and `booking` exposes customer emails, phone numbers, and payment amounts across guests unless filtered strictly by `WHERE guest_id = :current_user_guest_id`.

---

## 1.8 Sensitive Columns Guests Must Never See

A guest response model must never expose the following columns:
1. `account.password_hash` — Credential hash (Argon2/bcrypt).
2. `account.role` of staff/managers/owners.
3. `guest.guest_id` of other guests.
4. `guest.email` and `guest.phone` of other guests.
5. `payment.payment_id` of other guests.
6. `booking.guest_id` when inspecting public availability or property details.
7. `legacy_reservations.total_paid` / `guest_email` / `guest_phone` / `notes`.
8. `refresh_token.token_hash`.

---

## 1.9 Booking State Machine

There are **5 booking states**:
1. `confirmed` (Initial state upon creation)
2. `checked_in` (Guest has arrived)
3. `checked_out` (Stay completed)
4. `cancelled` (Booking cancelled prior to check-in)
5. `no_show` (Guest failed to arrive during check-in window)

### Legal State Transitions & Permissions Matrix:

```text
               ┌──────────────┐
               │  confirmed   │
               └──┬───┬────┬──┘
      cancel by   │   │    │  no-show by
  guest / manager │   │    │  staff / manager
                  ▼   │    ▼
      ┌───────────┐   │   ┌───────────┐
      │ cancelled │   │   │  no_show  │
      └───────────┘   │   └───────────┘
          check-in by │ staff / manager
                      ▼
              ┌──────────────┐
              │  checked_in  │
              └───────┬──────┘
         check-out by │ staff / manager
                      ▼
              ┌──────────────┐
              │ checked_out  │
              └──────────────┘
```

| Current State | Target State | Action Endpoint | Permitted Roles | Notes / Business Rule |
| :--- | :--- | :--- | :--- | :--- |
| `confirmed` | `checked_in` | `POST /bookings/{id}/check-in` | `staff`, `manager`, `owner` | Guest arrives; marks room as currently occupied. |
| `confirmed` | `cancelled` | `POST /bookings/{id}/cancel` | `guest` (own booking), `manager` (own property), `owner` | Cancellation releases room for other guests. |
| `confirmed` | `no_show` | `POST /bookings/{id}/no-show` | `staff`, `manager`, `owner` | Guest did not arrive; releases exclusion window. |
| `checked_in` | `checked_out` | `POST /bookings/{id}/check-out` | `staff`, `manager`, `owner` | Stay complete; enables review submission. |
| *Any other* | *Any other* | — | **REJECTED (400/409)** | Illegal transitions (e.g. `confirmed` → `checked_out`, `cancelled` → `checked_in`) are rejected. |

---

## 1.10 Schema Improvement Defense

**Proposed Schema Improvement**: Add an `idempotency_key VARCHAR(128) UNIQUE` and `created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()` to the `payment` table.

**Defense**:
When hotel staff process tablet payments or guests pay deposits over mobile connections, network drops frequently lead to retry requests. Without a unique idempotency key at the database level, retried HTTP requests risk executing double charges. Adding `idempotency_key` guarantees database-enforced deduplication, allowing the API to return the original transaction receipt safely upon retry.
