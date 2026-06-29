# 09 · Decisions (ADR Log)

> Architecture Decision Records. Referenced by `/eod`. Newest at top.
> Format: Context · Decision · Alternatives · Consequences.

These mirror the design-doc DD-1..DD-9 and HLD TD-1..TD-9; new decisions made
during the build are appended here first.

---

## ADR-0001 — Extend FSN x BIN with graph multi-hop signals (2026-06-29)

- **Context**: PS only correlates FSN x BIN (PHANTOM vs GENUINE). User wants an e2e
  solution using the WMS context repo.
- **Decision**: Add four additive signals (picker overlap, shared GRN batch,
  IRT/stocktake feedback, ATP cross-check), each grounded in a real WMS service.
- **Alternatives**: Stay strictly FSN x BIN (too shallow); full WMS extension
  (too broad for demo).
- **Consequences**: Richer root cause + clearer actions; deterministic verdict still
  works alone if the graph is unavailable.

---

## ADR-0012 — `failures_before` snapshot at suggestion time (2026-06-26)

- **Context**: To measure whether an action reduced INF failures, we need a pre-action
  baseline. Computing it retrospectively (after the action) is unreliable because more
  failures may arrive in between.
- **Decision**: Capture `failures_before = live COUNT` at `POST /feedback` creation time
  and store it immutably. `failures_after` is captured only when status transitions to
  `executed`.
- **Alternatives**: Compute baseline from historical data (complex); require caller to
  provide it (trusts the caller, not the system).
- **Consequences**: Accurate delta even if failures continue arriving before the action.
  Minor: the count is a point-in-time snapshot, not a windowed average.

---

## ADR-0013 — Lifecycle transitions enforced server-side (2026-06-26)

- **Context**: `recommendation_log` has a strict lifecycle. Without enforcement, ops
  could skip steps (e.g., `suggested→verified`) before capturing `failures_after`.
- **Decision**: `VALID_TRANSITIONS` dict in `feedback.py` maps each status to its only
  valid successor. `advance_status()` raises 400 if the requested transition doesn't match.
- **Alternatives**: Trust the client to send correct transitions (no enforcement).
- **Consequences**: Operational discipline enforced at API level; `failures_after` is
  always captured before `verified` can be reached.

---

## ADR-0010 — Two-stage LLM: Haiku routes, Sonnet reasons (2026-06-26)

- **Context**: NL questions vary widely — some need only SQL, some only graph, some both.
  Sending every question to Sonnet is expensive and slow.
- **Decision**: Haiku classifies first (SQL_ONLY/GRAPH_ONLY/SQL_GRAPH/OUT_OF_SCOPE).
  Sonnet only receives the tools it actually needs. OUT_OF_SCOPE skips Sonnet entirely.
- **Alternatives**: Single Sonnet call with all tools always (expensive); GPT-4o mini for
  routing (no Anthropic API unification).
- **Consequences**: ~10x cost reduction on routable questions; Haiku failure falls back
  to SQL_GRAPH (safe default).

---

## ADR-0011 — LLM query security: keyword deny-list, not ORM (2026-06-26)

- **Context**: Sonnet generates free-text SQL and nGQL. These are executed on real
  databases and must be constrained to read-only operations.
- **Decision**: Regex deny-list on DML/DDL keywords (`INSERT`, `UPDATE`, `DELETE`,
  `DROP`, etc.). Blocked queries return an error string to the model (not the user).
- **Alternatives**: ORM/prepared statements (can't apply to free-text LLM output);
  dedicated SQL parser (complex, dependency-heavy).
- **Consequences**: Effective for the most dangerous keywords. Model self-corrects.
  Does not catch all possible injection vectors — documented as a known limitation.

---

## ADR-0008 — Graph signals are additive, never blocking (2026-06-26)

- **Context**: Graph signals enrich the SQL verdict but must not block the API if
  NebulaGraph is slow, down, or a query fails.
- **Decision**: Each signal function returns `{}` on any failure. `enrich_signals()`
  wraps each in its own try/except and merges. `get_session()` yields `None` if
  the pool is uninitialised.
- **Alternatives**: Raise on graph failure (blocks API); background pre-fetch (complex).
- **Consequences**: Degraded signal coverage when graph is down, but diagnoses API
  always returns SQL verdicts. Failure is visible in logs.

---

## ADR-0009 — Enrich once per (wh, bin), not per (wh, bin, fsn) (2026-06-26)

- **Context**: A BIN with 5 failing FSNs would trigger 5 identical graph queries
  if enrichment were called per DiagnosisRow.
- **Decision**: Deduplicate (wh, bin) pairs before enrichment; store in `bin_signals`
  dict; all FSN rows for the BIN share the result.
- **Alternatives**: Per-row enrichment (simple but wasteful); async parallel queries
  (complex for demo scale).
- **Consequences**: Graph queries scale with unique BINs, not total (bin, fsn) rows.

---

## ADR-0006 — In-memory ETL watermark (2026-06-25)

- **Context**: The ETL sync needs to track the last `updated_at` it processed to avoid
  re-scanning the entire table every minute.
- **Decision**: Module-level `datetime` variable in `sync.py`, reset to epoch at startup.
- **Alternatives**: Persist in StarRocks table (adds a write dependency); persist in a file
  (adds filesystem dependency); Redis (adds another service).
- **Consequences**: First run after a restart always does a full sync. Acceptable for the demo.
  Production note is documented inline.

---

## ADR-0007 — FastAPI `lifespan` over deprecated `on_event` (2026-06-25)

- **Context**: `@app.on_event("startup")` was deprecated in FastAPI 0.93.
- **Decision**: Use `@asynccontextmanager` lifespan pattern.
- **Alternatives**: Keep `on_event` (works but suppresses deprecation warnings).
- **Consequences**: Cleaner startup/shutdown; aligns with current FastAPI best practices.

---

## ADR-0003 — BIN VID = compound `wh_id:label` in NebulaGraph (2026-06-25)

- **Context**: Multiple dark stores can have a BIN with the same physical label (e.g. F1-05-5D).
  Using label alone as the VID would merge them into a single node.
- **Decision**: Use `<reservation_warehouse_id>:<label>` as the BIN VID.
- **Alternatives**: Label only (collisions); separate property on the node (still needs unique VID).
- **Consequences**: VID is slightly longer, but graph traversals remain correct across warehouses.

---

## ADR-0004 — StarRocks DUPLICATE KEY for `pendency_mv` (2026-06-25)

- **Context**: The same (wh, bin, fsn) can produce multiple INF events at different times.
  StarRocks UNIQUE KEY would retain only one row per key.
- **Decision**: Use DUPLICATE KEY — every INF event row is retained.
- **Alternatives**: AGGREGATE KEY with `MAX(updated_at)` (loses event count); UNIQUE (wrong).
- **Consequences**: All historical events available for frequency counting; storage slightly higher.

---

## ADR-0005 — `grn_id` as column on `pendency_mv`, not a new StarRocks MV (2026-06-25)

- **Context**: The shared-inbound-batch graph signal needs to link FSNs to a GRN. In
  production this would be a join to the receiving service. PS guardrail: "no new MVs".
- **Decision**: Add `grn_id VARCHAR(64)` directly to the demo `pendency_mv` table.
- **Alternatives**: Separate StarRocks table (a new MV — violates guardrail); join at query time
  (requires a second table anyway).
- **Consequences**: Demo-only simplification clearly annotated as such. Production path is a join.

---

## ADR-0002 — Follow PS stack exactly; ignore the Java archetype (2026-06-29)

- **Context**: Repo seeded with a Java/Maven archetype; PS prescribes FastAPI + React
  + StarRocks + NebulaGraph.
- **Decision**: Build the PS stack; leave the Java archetype untouched/unused.
- **Alternatives**: Keep Java/Spring (fights the PS); mix stacks (friction, no benefit).
- **Consequences**: Clean alignment with the PS; the archetype is dead weight but harmless.

<!--
## ADR-XXXX — <title> (YYYY-MM-DD)
- **Context**:
- **Decision**:
- **Alternatives**:
- **Consequences**:
-->
