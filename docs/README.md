# Docs

Living documentation for the **BIN-FSN Stockout Diagnosis** project. Kept
continuously updated so anyone can see, in detail, what has been done and why.
Each area is split into subfiles so you can drill into any single topic.

## Structure

```
docs/
├── README.md                      # this file
├── journal/                       # running notes (chronological + by topic)
│   ├── README.md                  #   index
│   ├── progress-log.md            #   chronological master log
│   └── 00..09-*.md                #   topic files (infra, data, etl, api, ... decisions)
├── deliverables/
│   ├── HLD/                       # High-Level Design
│   │   ├── README.md · HLD.md
│   │   └── 01..06-*.md            #   context, architecture, flows, extension, decisions, quality
│   └── LLD/                       # Low-Level Design
│       ├── README.md · LLD.md
│       └── 01..09-*.md            #   layout, schemas, algorithm, signals, api, etl, llm, frontend, security
└── code-walkthroughs/             # per-module "what the code does" (written after coding)
    └── README.md
```

## Where to look

| If you want to know... | Read |
|------------------------|------|
| Project context, progress, doc health | [../CLAUDE.md](../CLAUDE.md) |
| What happened, step by step | [journal/progress-log.md](journal/progress-log.md) |
| A specific topic's notes | `journal/0x-*.md` (see [journal/README.md](journal/README.md)) |
| The architecture | [deliverables/HLD/README.md](deliverables/HLD/README.md) |
| Exact schemas / endpoints / algorithms | [deliverables/LLD/README.md](deliverables/LLD/README.md) |
| A beginner-friendly step-by-step learning path | [learning/README.md](learning/README.md) |
| Why each technical decision was made | [deliverables/HLD/05-technical-decisions.md](deliverables/HLD/05-technical-decisions.md) · [journal/09-decisions.md](journal/09-decisions.md) |
| What a built module actually does | [code-walkthroughs/README.md](code-walkthroughs/README.md) |

## Maintenance rule

After writing or changing code: (1) add/update the matching **code walkthrough**,
(2) update the relevant **HLD/LLD** subfile, (3) add a **journal** entry, and
(4) tick the milestone boxes in [../CLAUDE.md](../CLAUDE.md) §7 and
[../design/milestones.md](../design/milestones.md). The `.claude/commands/`
rituals (`/sod`, `/eod`, `/docs-review`, `/milestone-complete`) help enforce this.

## Related (outside docs/)

- [../explanation/context-repository.md](../explanation/context-repository.md) — what the WMS context repo is
- [../design/design-doc.md](../design/design-doc.md) — design decisions
- [../design/milestones.md](../design/milestones.md) — stepwise milestone plan + checklist
