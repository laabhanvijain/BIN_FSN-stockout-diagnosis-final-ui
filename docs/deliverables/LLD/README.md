# LLD — Low-Level Design

Implementation-level deliverable, split into focused subfiles. `LLD.md` remains the
consolidated overview. Sections marked _(planned)_ fill in as milestones complete.

| File | Topic | Milestone |
|------|-------|-----------|
| [LLD.md](LLD.md) | Consolidated LLD overview | — |
| [01-repo-layout.md](01-repo-layout.md) | Folder/module structure | M0 |
| [02-data-schemas.md](02-data-schemas.md) | StarRocks + NebulaGraph schemas | M2 |
| [03-verdict-algorithm.md](03-verdict-algorithm.md) | Verdict SQL & scoring | M5 |
| [04-graph-signals.md](04-graph-signals.md) | nGQL signal queries | M6 |
| [05-api-contracts.md](05-api-contracts.md) | Endpoint request/response | M5/M7/M8 |
| [06-etl.md](06-etl.md) | Sync job design | M4 |
| [07-llm-agent.md](07-llm-agent.md) | Tools, models, citation enforcement | M7 |
| [08-frontend.md](08-frontend.md) | React components & state | M9 |
| [09-security.md](09-security.md) | Secrets, query whitelisting, validation | cross-cutting |

After coding a module, fill its LLD subfile and write the matching
[code walkthrough](../../code-walkthroughs/).
