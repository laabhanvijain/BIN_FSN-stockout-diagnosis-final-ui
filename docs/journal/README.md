# Journal

Running notes split into topic files so you can drill into any one thing.
`progress-log.md` is the chronological master log; the numbered files are
topic-specific and grow as work proceeds.

| File | What it covers |
|------|----------------|
| [progress-log.md](progress-log.md) | Chronological master log (newest first) |
| [00-overview.md](00-overview.md) | Project summary & how the journal is organized |
| [01-infra.md](01-infra.md) | Docker, StarRocks, NebulaGraph setup notes |
| [02-data-and-schema.md](02-data-and-schema.md) | Schemas, dummy data generation |
| [03-etl.md](03-etl.md) | StarRocks -> NebulaGraph sync |
| [04-backend-api.md](04-backend-api.md) | FastAPI endpoints |
| [05-graph-signals.md](05-graph-signals.md) | Multi-hop root-cause signals |
| [06-llm-assistant.md](06-llm-assistant.md) | LLM tool-agent & citations |
| [07-frontend.md](07-frontend.md) | React UI |
| [08-troubleshooting.md](08-troubleshooting.md) | Gotchas, errors, fixes |
| [09-decisions.md](09-decisions.md) | ADR-style decision records |

**Convention**: each topic file uses dated subsections (newest at top). When a
milestone touches a topic, add a dated note here and a master entry in `progress-log.md`.
