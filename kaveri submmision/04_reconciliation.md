# Interlude — Specification Reconciliation & Architecture Audit

## 4.1 Specification Alignment & Audit

As specified in the assignment guidelines, the original specification `03_openapi_original.yaml` and authorization matrix `03_authorization_matrix.md` were finalized and committed prior to this reconciliation step.

### Path & Operation Comparison:

| Path | Method | Status in Original | Status in Final | Design Rationale & Business Rules |
| :--- | :--- | :--- | :--- | :--- |
| `/auth/register` | `POST` | Present | Preserved | Creates self-service guest account; rejects role escalation. |
| `/auth/login` | `POST` | Present | Preserved | Authenticates with bcrypt/Argon2; rate limited against brute force. |
| `/auth/refresh` | `POST` | Present | Preserved | Rotates refresh token; revokes token family on reuse. |
| `/auth/logout` | `POST` | Present | Preserved | Revokes active refresh token. |
| `/me` | `GET` | Present | Preserved | Returns caller identity, role, and property scope. |
| `/properties` | `GET` | Present | Preserved | Public property catalog. |
| `/properties/{id}` | `GET` | Present | Preserved | Public property details with room types. |
| `/rooms/availability` | `GET` | Present | Preserved | Uses PostgreSQL GiST exclusion logic; respects checkout=checkin date boundaries. |
| `/bookings` | `GET` | Present | Preserved | Scoped listing with whitelist sorting and limit/offset pagination. |
| `/bookings` | `POST` | Present | Preserved | Atomic transaction (occupancy trigger check, booking insert, deposit calculation & payment insert). |
| `/bookings/{id}` | `GET` | Present | Preserved | Privacy-preserving lookup (returns 404 for other guests' bookings). |
| `/bookings/{id}/check-in` | `POST` | Present | Preserved | Enforces state transition `confirmed` → `checked_in`. |
| `/bookings/{id}/check-out` | `POST` | Present | Preserved | Enforces state transition `checked_in` → `checked_out`. |
| `/bookings/{id}/cancel` | `POST` | Present | Preserved | Enforces state transition `confirmed` → `cancelled`. |
| `/bookings/{id}/payments` | `GET` | Present | Preserved | Lists payment breakdown. |
| `/bookings/{id}/payments` | `POST` | Present | Preserved | Records instalment payments; deduplicates via `Idempotency-Key`. |
| `/bookings/{id}/review` | `POST` | Present | Preserved | Permitted only after `checked_out`; enforces one review per booking. |
| `/reports/occupancy` | `GET` | Present | Preserved | SQL-computed occupancy rate (manager scoped to own property; owner cross-property). |
| `/reports/revenue` | `GET` | Present | Preserved | SQL-computed ADR and RevPAR financial metrics. |

---

## 4.2 Defensible Design Decisions & Error Envelope

1. **Explicit State Action Endpoints**:
   Using `/bookings/{id}/check-in`, `/check-out`, `/cancel` provides explicit intent, distinct audit trails, and strict role permissions compared to a loose `PATCH /bookings/{id}`.
2. **Unified Error Envelope**:
   Every error returns `{"error": {"code": "...", "message": "..."}}`.
3. **Database-Driven Nightly Rate**:
   Client-supplied nightly rates are completely ignored in favor of server-side rate plan lookups in `rate` table.

The final operational OpenAPI 3.1.0 specification is codified in `05_openapi_final.yaml`.
