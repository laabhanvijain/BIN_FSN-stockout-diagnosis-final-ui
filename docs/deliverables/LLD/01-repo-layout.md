# LLD 01 · Repo Layout (planned)

```
BIN-FSN-stockout-diagnosis/
├── backend/
│   ├── main.py                 # FastAPI entrypoint
│   ├── requirements.txt
│   ├── routers/                # diagnoses.py, ask.py, feedback.py
│   ├── services/               # diagnosis.py, graph.py, llm.py
│   ├── etl/sync.py             # StarRocks -> NebulaGraph (1-min)
│   └── db/                     # starrocks.py, nebula.py
├── frontend/                   # React app
├── data/
│   ├── schema/                 # DDL (SQL + nGQL)
│   └── generate_dummy_data.py
└── infra/docker-compose.yml
```

_Status: done (M0, committed 2026-06-25)._
