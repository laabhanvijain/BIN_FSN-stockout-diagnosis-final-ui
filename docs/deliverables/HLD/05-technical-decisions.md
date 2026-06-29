# HLD 05 · Technical Decisions & Rationale

> Options -> choice -> why -> risk. Mirrors design-doc DD-1..DD-9. ADR detail in
> [../../journal/09-decisions.md](../../journal/09-decisions.md). Append new decisions as the build proceeds.

| ID | Decision | Options considered | Why chosen | Risk / mitigation |
|----|----------|--------------------|-----------|-------------------|
| **TD-1** | Keep PS verdict logic as deterministic core | ML re-derivation vs PS SQL CASE | Auditable, reproducible, PS-validated; ML out of scope | Rigid thresholds -> expose raw counts for override |
| **TD-2** | Extend with graph multi-hop signals | Strict FSN x BIN vs graph extension | Explains why + what to do; user asked for e2e | Over-engineering -> additive, verdict stands alone |
| **TD-3** | Two stores: StarRocks + NebulaGraph | SQL-only vs graph-only vs both | Aggregation in SQL, multi-hop in graph (PS-prescribed) | Ops overhead -> thin ETL + Docker |
| **TD-4** | Single source table, no new MVs | New MV vs reuse pendency_mv | Hard PS guardrail | GRN join uncertainty -> demo column, graceful degradation |
| **TD-5** | FastAPI with 3 endpoints | Monolith vs minimal API | Matches PS architecture; fast to build | — |
| **TD-6** | LLM tool-agent with mandatory citations | Free-form vs tool-grounded | Citation is a PS success metric; prevents hallucination | Cost -> Haiku-first routing |
| **TD-7** | `recommendation_log` for closed loop | No tracking vs dedicated table | PS requires audit-ready evidence linkage | — |
| **TD-8** | Follow PS stack exactly, ignore Java archetype | Keep Java vs PS Python+JS | PS prescribes stack; archetype was scaffolding | — |
| **TD-9** | Seeded ground-truth dummy data | Random vs engineered scenarios | Deterministic demo + accuracy measurement | — |
