# 04 · Backend API (FastAPI)

> Endpoint notes. Milestones: M5 (/diagnoses), M7 (/ask), M8 (/feedback).
> Detail: [../deliverables/LLD/05-api-contracts.md](../deliverables/LLD/05-api-contracts.md).

_Status: M5 (`GET /diagnoses`) ✅ M7 (`/ask`) ✅ M8 (`/feedback`) ✅ — all done 2026-06-26._

---

## 2026-06-26 — M5 complete: `GET /diagnoses` endpoint

### What was done

**`backend/services/diagnosis.py`**
- `DiagnosisRow` dataclass with `graph_signals: dict = {}` placeholder (M6 fills it).
- `_VERDICT_SQL`: 3-CTE PS query — `inf` (raw counts), `bin_sum` (distinct FSNs per BIN),
  `fsn_sum` (distinct BINs per FSN) → CASE verdict.
- `_compute_recovery()`: `recovery_pct = orders_impacted / Σ orders_in_wh * 100`.
  Filter is applied post-SQL so the denominator uses the full warehouse population.
- `get_diagnoses(warehouse_id, window_days)`: runs SQL, applies optional wh filter,
  builds `DiagnosisRow` list.

**`backend/routers/diagnoses.py`**
- `GET /api/diagnoses` with `warehouse_id?` and `window_days` (1–30, default 1).
- FastAPI validates `window_days` range automatically (422 on bad input).
- Returns `[asdict(r) for r in rows]`.

**`backend/main.py`** (updated)
- Diagnoses router registered: `app.include_router(diagnoses.router, prefix="/api")`.

### Technical decisions

| Decision | Choice | Why |
|----------|--------|-----|
| PS SQL verbatim | No rewrite | PS is the spec |
| Warehouse filter post-SQL | Python | Recovery denominator uses full-wh population |
| `graph_signals: dict = {}` in M5 | Empty placeholder | API shape stable; M6 fills without contract change |
| `dataclasses.asdict` | Not Pydantic | Simpler; Pydantic is a future upgrade |

### Files changed

- Created: `backend/services/diagnosis.py`, `backend/routers/diagnoses.py`
- Updated: `backend/main.py`

### Status: committed 2026-06-26

---

## 2026-06-26 — M8 complete: closed-loop feedback (/feedback)

### What was done

**`backend/services/feedback.py`**
- `list_recommendations(warehouse_id?)`: fetches all `recommendation_log` rows,
  computes `failures_ceased = failures_before - failures_after` inline for rows
  that have both values, serialises datetime fields to ISO strings.
- `create_recommendation(wh, bin, fsn, verdict, evidence_ref)`: inserts a new row
  with `status='suggested'`; captures `failures_before` from a live `pendency_mv`
  COUNT at creation time so the pre-action baseline is locked in immediately.
- `advance_status(rec_id, new_status)`: validates lifecycle transition
  (`suggested→acknowledged→executed→verified`); on `executed` captures
  `failures_after` from live pendency_mv; on `verified` sets `resolved_at`.

**`backend/routers/feedback.py`**
- `GET /api/feedback?warehouse_id=` — list with `failures_ceased` computed.
- `POST /api/feedback` — create recommendation; Pydantic validates `verdict` enum.
- `PATCH /api/feedback/{id}/status` — advance lifecycle; 400 on invalid transition.

**`backend/main.py`** — feedback router registered.

### Technical decisions

| Decision | Choice | Why |
|----------|--------|-----|
| `failures_before` captured at creation | Live COUNT at POST time | Locks in pre-action baseline; avoids retroactive computation |
| `failures_after` captured at `executed` | Live COUNT at PATCH time | Measures actual post-action state, not stale data |
| Lifecycle validated server-side | `VALID_TRANSITIONS` dict | Prevents skipping steps (e.g. `suggested→verified` directly) |
| `failures_ceased` computed in Python | Post-query arithmetic | Keeps SQL simple; StarRocks DUPLICATE KEY complicates UPDATE-then-SELECT |

### Files changed

- Created: `backend/services/feedback.py`, `backend/routers/feedback.py`
- Updated: `backend/main.py`

### Status: committed 2026-06-26

<!-- ## YYYY-MM-DD — <what happened> -->
