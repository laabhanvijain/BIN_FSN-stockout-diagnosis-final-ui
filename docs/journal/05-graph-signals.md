# 05 · Graph Signals (multi-hop root cause)

> Milestone: M6. Detail: [../deliverables/LLD/04-graph-signals.md](../deliverables/LLD/04-graph-signals.md).

_Status: M6 done 2026-06-26._

---

## 2026-06-26 — M6 complete: graph signal enrichment

### What was done

**`backend/services/graph.py`** — 4 signals, all additive:

| Signal | nGQL pattern | Returns when |
|--------|-------------|-------------|
| `picker_concentration` | `Picker -[ASSIGNED_TO]-> BIN` | dominant picker share ≥ 0.7 |
| `shared_grn` | `FSN -[FAILED_AT]-> BIN` + `FSN -[RECEIVED_IN]-> GRN` (2-hop) | all failing FSNs share 1 GRN |
| `stocktake_done` | `BIN -[STOCKTAKE]-> Variance` | STOCKTAKE edge exists |
| `atp_likely_zero` | proxy: `distinct_bins >= threshold` | GENUINE_STOCKOUT candidates |

**`backend/services/diagnosis.py`** (updated)
- Deduplicates (wh, bin) pairs before calling `enrich_signals()` — 1 graph call per BIN,
  not N calls for N FSNs.
- `bin_signals` dict keyed by `(wh, bin)` — shared across all FSN rows for that BIN.

### Technical decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Additive signals, `{}` on failure | Return empty dict | Graph must never block SQL verdict |
| Enrich once per (wh, bin) | Deduplicate | N FSNs per BIN → N graph calls → 1 |
| Per-signal try/except | Individual wrapping | One bad signal ≠ suppress the rest |
| Picker threshold 0.7 | Module constant | Clearly annotated; easy to promote to settings |
| ATP proxy (stub) | `distinct_bins` logic | No ATP service in scope; labelled for production |

### Files changed

- Created: `backend/services/graph.py`
- Updated: `backend/services/diagnosis.py` (import + enrich wiring)

### Status: committed 2026-06-26

<!-- ## YYYY-MM-DD — <what happened> -->
