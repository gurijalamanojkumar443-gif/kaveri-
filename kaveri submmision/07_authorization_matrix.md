# Stage 7 — Authorization Matrix

## 7.1 Role Definitions

| Role | Scope | Assigned property_id |
|------|-------|----------------------|
| `guest` | Own bookings, payments, reviews only | NULL |
| `staff` | Property-scoped — check-in/check-out, view bookings | `property_id` |
| `manager` | Property-scoped — all staff actions + cancel + reports | `property_id` |
| `owner` | All properties, all actions | NULL |

---

## 7.2 Complete Authorization Matrix

Legend: **✅ Allowed** | **❌ Forbidden (403)** | **🔒 Auth Required (401)** | **👁 Scoped (own only)**

| Endpoint | Method | No Token | guest | staff | manager | owner |
|----------|--------|----------|-------|-------|---------|-------|
| `GET /properties` | Read | ✅ Public | ✅ | ✅ | ✅ | ✅ |
| `GET /properties/{id}` | Read | ✅ Public | ✅ | ✅ | ✅ | ✅ |
| `GET /rooms/availability` | Read | ✅ Public | ✅ | ✅ | ✅ | ✅ |
| `POST /auth/register` | Write | ✅ Public | ✅ | ✅ | ✅ | ✅ |
| `POST /auth/login` | Write | ✅ Public | ✅ | ✅ | ✅ | ✅ |
| `POST /auth/refresh` | Write | ✅ Public | ✅ | ✅ | ✅ | ✅ |
| `POST /auth/logout` | Write | 🔒 | ✅ | ✅ | ✅ | ✅ |
| `GET /auth/me` | Read | 🔒 | 👁 own | ✅ | ✅ | ✅ |
| `GET /bookings` | Read | 🔒 | 👁 own | 👁 prop | 👁 prop | ✅ all |
| `POST /bookings` | Write | 🔒 | ✅ own guest | ✅ on behalf | ✅ on behalf | ✅ |
| `GET /bookings/{id}` | Read | 🔒 | 👁 own→404 | 👁 prop | 👁 prop | ✅ |
| `POST /bookings/{id}/check-in` | Write | 🔒 | ❌ 403 | ✅ own prop | ✅ own prop | ✅ |
| `POST /bookings/{id}/check-out` | Write | 🔒 | ❌ 403 | ✅ own prop | ✅ own prop | ✅ |
| `POST /bookings/{id}/cancel` | Write | 🔒 | ✅ own | ❌ 403 | ✅ own prop | ✅ |
| `GET /bookings/{id}/payments` | Read | 🔒 | 👁 own→404 | 👁 prop | 👁 prop | ✅ |
| `POST /bookings/{id}/payments` | Write | 🔒 | ✅ own | ✅ prop | ✅ prop | ✅ |
| `POST /bookings/{id}/review` | Write | 🔒 | ✅ own checked_out | ❌ 403* | ❌ 403* | ✅ |
| `GET /reports/occupancy` | Read | 🔒 | ❌ 403 | ❌ 403 | ✅ own prop | ✅ |
| `GET /reports/revenue` | Read | 🔒 | ❌ 403 | ❌ 403 | ✅ own prop | ✅ |

*Reviews: staff/manager accessing a booking they don't "own" as a guest get 404 (privacy), but can't review as a guest identity.

---

## 7.3 Privacy Rules

| Principle | Implementation |
|-----------|----------------|
| Guest A cannot discover Guest B's booking exists | Returns **404**, not 403, for cross-guest booking access |
| Sensitive columns never exposed | `password_hash`, `token_hash`, `replaced_by` never in any response model |
| Email enumeration blocked | Login error message is identical for wrong email and wrong password |
| Property cross-access blocked | Manager requesting another property's data returns **403** |

---

## 7.4 Test Results — 4-Environment Verification

Tests run via `pytest tests/test_authorization.py` with all 4 tokens:

| Test | guest | staff | manager | owner |
|------|-------|-------|---------|-------|
| Public endpoints accessible | ✅ | ✅ | ✅ | ✅ |
| `/auth/me` requires token | 401 | 401 | 401 | 401 |
| Guest sees own bookings only | ✅ | — | — | — |
| Staff cannot cancel booking | — | 403 ✅ | — | — |
| Guest cannot check-in | 403 ✅ | — | — | — |
| Manager cross-property blocked | — | — | 403 ✅ | — |
| Staff blocked from reports | — | 403 ✅ | — | — |
| Guest blocked from reports | 403 ✅ | — | — | — |
| Owner sees all occupancy | — | — | — | ✅ |
| Manager report scoped | — | — | prop_1 ✅ | — |
| No password hash in responses | ✅ | ✅ | ✅ | ✅ |

All authorization matrix tests: **82/82 passed.**
