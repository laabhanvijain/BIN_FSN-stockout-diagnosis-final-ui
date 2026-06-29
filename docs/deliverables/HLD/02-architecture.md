# HLD 02 · Architecture

```mermaid
flowchart TD
  Manager["Store Manager (browser)"] --> UI["React UI"]
  UI -->|REST| API["FastAPI Backend"]
  API -->|SQL| SR["StarRocks<br/>pendency_mv (read-only)"]
  API -->|nGQL| NG["NebulaGraph"]
  SR -->|1-min ETL| NG
  API -->|tools| LLM["Claude Haiku/Sonnet"]
  API --> RL[("recommendation_log")]
```

## Components

| Component | Tech | Responsibility |
|-----------|------|----------------|
| UI | React | Diagnoses Table, Assistant, Feedback |
| Backend | FastAPI | `/diagnoses`, `/ask`, `/feedback`; LLM orchestration |
| Analytics | StarRocks | Aggregate INF; verdict counts |
| Graph | NebulaGraph | Multi-hop signals |
| ETL | Python cron (1-min) | StarRocks -> graph |
| LLM | Claude Haiku/Sonnet | Route/reason; cite |
| Infra | Docker Compose | One-command bring-up |

## Boundaries

This system is read-only over the source table and owns only `recommendation_log`
and the NebulaGraph projection. The WMS pipeline remains the source of truth.
