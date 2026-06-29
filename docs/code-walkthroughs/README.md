# Code Walkthroughs

Per-module explanations of **what the code actually does**, written **after** each
module is coded. These are the human-readable companion to the source — what each
file/function does, how data flows through it, and why it's built that way.

**Rule**: whenever code is written or significantly changed, add/update the matching
walkthrough here, update the relevant [LLD](../deliverables/LLD/) subfile, and add a
journal entry.

## Index

| File | Module | Status |
|------|--------|--------|
| [infra-docker-compose.md](infra-docker-compose.md) | `infra/docker-compose.yml`, Dockerfiles | written |
| [data-schema.md](data-schema.md) | `data/schema/starrocks.sql` + `nebula.ngql` | written |
| [data-generator.md](data-generator.md) | `data/generate_dummy_data.py` | written |
| [etl-sync.md](etl-sync.md) | `backend/etl/sync.py` | written |
| [backend-diagnoses.md](backend-diagnoses.md) | `backend/services/diagnosis.py` | written |
| [backend-graph-signals.md](backend-graph-signals.md) | `backend/services/graph.py` | written |
| [backend-ask-llm.md](backend-ask-llm.md) | `backend/services/llm.py` | written |
| [backend-feedback.md](backend-feedback.md) | `backend/services/feedback.py` | written |
| [frontend.md](frontend.md) | `frontend/src/` | written |

---

## Walkthrough template

```markdown
# <Module Name> — Code Walkthrough

> Source: `<path(s)>` · Milestone: M<n> · Last updated: YYYY-MM-DD

## What it does
<one-paragraph summary>

## Key files / functions
| File / function | Responsibility |
|-----------------|----------------|

## Data flow
<step-by-step or diagram>

## Why it's built this way
<decisions, links to ADR/TD>

## Gotchas
<edge cases, things to watch>
```
