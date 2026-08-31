# Stage 2 — Authentication Architecture & Identity Design

## 2.1 Identity Storage: `accounts` vs `guests`

**Choice Selected: Option B (`accounts`)**

### Defense:
1. **Most Guests Never Log In**: Many guests book via phone, walk-in, OTAs, or front desk reservations without ever creating an online login account. Coupling password credentials and authentication fields directly into the `guest` table would pollute customer demographic data with null hashes and auth metadata.
2. **Staff Are Not Guests**: Staff and managers work for Kaveri Stays properties and must not be forced into a table designed for hotel customers (which expects loyalty details, guest preferences, stay histories, etc.).
3. **Role Fluidity (Guest Becoming Staff)**: If an existing guest is subsequently hired as property staff, separating `account` from `guest` prevents schema corruption. An `account` record cleanly specifies authentication credentials, role (`staff`), and property association (`property_id = 1`), while preserving any historical customer stays in `guest`.

---

## 2.2 Role Hierarchy & Database Scoping Constraints

We model **4 distinct roles**:
1. `guest`: Customer booking stays. Has no property association (`property_id IS NULL`). Can access only own profile, bookings, payments, and reviews.
2. `staff`: Front-desk tablet operator. **Must belong to exactly one property** (`property_id NOT NULL`). Can check guests in/out, take payments, and view property rooms.
3. `manager`: Property supervisor. **Must belong to exactly one property** (`property_id NOT NULL`). Can view property-specific financial reports, manage rooms, and view staff/bookings for their property.
4. `owner`: Global executive. Has no property restriction (`property_id IS NULL`). Has cross-property read and report capabilities across Coorg, Ooty, and Alleppey.

### Database Enforcement:
Enforced in PostgreSQL via a table CHECK constraint:
```sql
CONSTRAINT check_role_property_scope CHECK (
    (role IN ('staff', 'manager') AND property_id IS NOT NULL) OR
    (role IN ('guest', 'owner') AND property_id IS NULL)
)
```
Any attempt to insert a staff member with `property_id = NULL` or an owner with `property_id = 1` immediately fails with `23514` (check constraint violation).

---

## 2.3 Authentication DDL Summary

Implemented in `02_auth_schema.sql`:
- Table `account` (Primary Key, Foreign Keys to `property` and `guest`, unique constraint on `email`, check constraint on role scope).
- Table `refresh_token` (Primary Key, Foreign Key to `account`, unique `token_hash`, rotation tracking with `replaced_by` and `revoked`).

---

## 2.4 Password Hashing & Verification Cost

### Algorithm Chosen:
- **Primary Algorithm**: `bcrypt` (cost factor $rounds = 12$) / `Argon2id` ($time\_cost=3, memory\_cost=65536, parallelism=4$).

### Latency Measurement:
- **Bcrypt (cost factor 12)**:
  - Hash computation latency: **~266.47 ms**
  - Verification latency: **~266.53 ms**
- **Argon2id (64MB memory cost)**:
  - Hash computation latency: **~85.91 ms**
  - Verification latency: **~82.81 ms**

### Reason:
Bcrypt with 12 rounds provides an optimal balance between brute-force resistance (making GPU-based dictionary attacks prohibitively expensive) and server throughput for interactive web logins (~250ms verification overhead).

---

## 2.5 Registration & Privilege Escalation Prevention

- Endpoint: `POST /auth/register`
- **Rule**: Public self-service registration unconditionally assigns `role = "guest"` and `property_id = NULL`.
- If an untrusted caller submits:
  ```json
  {
    "email": "attacker@evil.com",
    "password": "Password123!",
    "name": "Attacker",
    "role": "owner"
  }
  ```
  The Pydantic input schema `RegisterRequest` omits the `role` field entirely, and the route handler forces `role = "guest"`. Staff, manager, and owner accounts can only be provisioned by authorized administrative procedures.

---

## 2.6 JWT Access Token Claims

The access token payload includes only minimal, non-sensitive operational claims:

```json
{
  "sub": "8",
  "account_id": 8,
  "guest_id": 1,
  "email": "aarav.sharma@example.com",
  "role": "guest",
  "property_id": null,
  "name": "Aarav Sharma",
  "iss": "kaveri-stays-api",
  "iat": 1787985000,
  "exp": 1787985900,
  "jti": "d3b07384-d113-4ec4-9c0e-49b04ab6e626"
}
```

### Rationale for Claims:
1. `sub`: Standard subject identifier (account ID string).
2. `account_id` / `guest_id`: Enables fast route authorization without extra SQL lookups.
3. `role`: Enables instant dependency permission checks (`guest`, `staff`, `manager`, `owner`).
4. `property_id`: Scopes staff and manager requests to their designated resort.
5. `exp`: Short-lived expiration (15 minutes).
6. `jti`: Unique JWT ID to prevent token replay.
7. *No password hashes, internal secret keys, or personally identifiable financial data are ever stored in the JWT*.

---

## 2.7 Refresh Token Rotation & Revocation

- **Access Token Expiry**: 15 minutes.
- **Refresh Token Expiry**: 7 days (stored server-side in `refresh_token` table as SHA-256 hash).
- **Rotation on Use (`POST /auth/refresh`)**:
  1. The client presents the raw refresh token.
  2. The server hashes the token and queries `refresh_token`.
  3. If the token is expired or `revoked = TRUE`, the request fails with `401 Unauthorized`.
  4. If an already-rotated token is reused (token reuse attack), the server flags the entire token family as compromised and revokes all refresh tokens for that account.
  5. If valid, the current token is marked `revoked = TRUE` and `replaced_by = <new_token_hash>`, and a new access token and refresh token pair are returned.
- **Logout (`POST /auth/logout`)**:
  - Sets `revoked = TRUE` on the active refresh token.

---

## 2.8 Fired Manager Mitigation & Immediate Revocation

### Scenario:
A manager is terminated while holding an unexpired 15-minute access token.

### Implementation:
1. When a user is deactivated or fired, `account.is_active` is set to `FALSE` in PostgreSQL, and all their `refresh_tokens` are deleted or revoked.
2. For sensitive write and reporting routes, the FastAPI dependency `get_current_active_user` verifies `account.is_active == True` against the database session or token blacklist cache.
3. If an access token with `is_active == False` is presented, the API immediately rejects the call with `401 Unauthorized` (`ACCOUNT_DEACTIVATED`).

---

## 2.9 Property Scope: Token vs Database Lookup

### Decision: Token Claims Validated by Database Dependencies

**Design**:
- Property scope (`property_id`) is embedded into the token for stateless O(1) authorization checks.
- If a manager is transferred from Ooty (property 2) to Coorg (property 1) mid-shift:
  - The database `account.property_id` is updated to `1`.
  - When the manager refreshes their token via `POST /auth/refresh`, the newly issued access token immediately contains `property_id: 1`.
  - For critical cross-property actions, the route dependency verifies that the user's active property ID in the database matches the requested resource.

---

## 2.10 Environment Configuration & Startup Security

We implement strict environment management:
- `.env.example`: Committed template with placeholder keys and no secrets.
- `.env`: Real secrets for local runtime (ignored by `.gitignore`).
- **Fail Loudly Rule**: In `app/config.py`, `SECRET_KEY` and `DATABASE_URL` are required fields in `pydantic_settings.BaseSettings`. If `SECRET_KEY` is missing or empty, application startup raises `ValidationError` / crashes immediately.

---

## 2.11 Swagger UI Authentication

The OpenAPI specification configures `securitySchemes` with `HTTPBearer`:
```yaml
components:
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
```
In FastAPI, `fastapi.security.HTTPBearer()` is attached to all protected routes, rendering the interactive padlock icon in `/docs` and allowing developers to paste real Bearer JWT tokens directly into Swagger UI.

---

## 2.12 Algorithm Selection: HS256 vs RS256

**Choice for Current Phase: HS256 (HMAC with SHA-256)**

### Defense:
1. **Single Backend Architecture**: The Kaveri Stays API is the sole issuer and consumer of authentication tokens. Symmetric HMAC-SHA256 (HS256) is fast, straightforward, and secure when backed by a cryptographically strong 256-bit secret key.
2. **Algorithm Hardening**: The API explicitly restricts `jwt.decode(..., algorithms=["HS256"])`, strictly preventing the infamous `alg: "none"` exploit or public key confusion attacks.

### When to Switch to RS256:
Kaveri Stays should transition to RS256 (Asymmetric RSA Public/Private Key Pairs) when:
- Multiple decoupled microservices (e.g. tablet POS services, mobile app gateways, partner hotel syndication APIs) need to verify tokens independently without sharing the master signing secret.
- An external Identity Provider (e.g. Keycloak, Auth0, Okta) is integrated with public JWKS endpoints (`/.well-known/jwks.json`).
