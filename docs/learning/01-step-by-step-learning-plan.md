# Step-By-Step Learning Plan

This plan assumes you are a beginner and do not know the tech stack yet.

The learning goal is:

> Be able to explain, modify, debug, extend, and defend every important
> architectural and technical decision in this project.

## How To Study

Use this loop for every phase:

1. Read the beginner explanation in this folder.
2. Learn the prerequisite concepts.
3. Open the listed files.
4. Trace one real runtime example.
5. Answer the checkpoint questions.
6. Do the small exercise.
7. Only then move to the next phase.

## Phase 0: Project Orientation

### What You Learn

- What problem the project solves.
- What the major folders are.
- What each system component does at a high level.

### Files To Read

1. `AGENTS.md`
2. `README.md`
3. `docs/learning/00-overall-flow.md`
4. `design/design-doc.md`

### Prerequisite Concepts

- What a web app is.
- What a backend is.
- What a frontend is.
- What a database is.

### Complexity

Low.

### Final Outcome

You can explain the project in one minute without mentioning code details.

### Checkpoint Questions

1. What is an INF event?
2. What is the difference between an FSN and a BIN?
3. Why does the project need both a UI and a backend?
4. What are the four possible verdicts?
5. Why is this useful to warehouse/store operators?

### Exercise

Write a 5-line explanation of the project in your own words.

## Phase 1: Warehouse Domain And Business Rules

### What You Learn

- Why pick failures happen.
- What phantom inventory means.
- What genuine stockout means.
- How the deterministic verdict rule works.

### Files To Read

1. `design/design-doc.md`
2. `docs/deliverables/HLD/01-context-and-goals.md`
3. `docs/deliverables/LLD/03-verdict-algorithm.md`

### Prerequisite Concepts

- Basic counting.
- Grouping by item and location.
- The idea of a rule-based classifier.

### Complexity

Medium.

### Final Outcome

You can manually classify small examples before seeing the code.

### Checkpoint Questions

1. If five different FSNs fail in one BIN, what verdict is likely?
2. If one FSN fails in three different BINs, what verdict is likely?
3. When do we call something `DUAL`?
4. Why is `AMBIGUOUS` useful instead of forcing a verdict?
5. What action should follow a phantom inventory verdict?

### Exercise

Create three fake failure examples and assign verdicts manually.

## Phase 2: Data Storage Basics

### What You Learn

- Why the project uses StarRocks.
- Why the project uses NebulaGraph.
- What tables, vertices, and edges mean.
- How demo data is shaped.

### Files To Read

1. `data/schema/starrocks.sql`
2. `data/schema/nebula.ngql`
3. `data/generate_dummy_data.py`
4. `docs/deliverables/LLD/02-data-schemas.md`

### Prerequisite Concepts

- Table: rows and columns.
- Primary key.
- SQL query.
- Graph: node/vertex and edge.

### Complexity

High.

### Final Outcome

You can explain what data exists in StarRocks and what relationships exist in
NebulaGraph.

### Checkpoint Questions

1. What table stores raw INF-like events?
2. What table stores recommendation feedback?
3. What is a graph vertex in this project?
4. What is a graph edge in this project?
5. Why is a graph useful for picker or GRN analysis?

### Exercise

Pick one generated dummy row and identify which graph vertices and edges it
should create.

## Phase 3: Backend Startup And Configuration

### What You Learn

- How the FastAPI backend starts.
- How configuration is loaded.
- How the app connects to StarRocks and NebulaGraph.
- How the background ETL scheduler starts.

### Files To Read

1. `backend/main.py`
2. `backend/config.py`
3. `backend/db/starrocks.py`
4. `backend/db/nebula.py`
5. `backend/requirements.txt`

### Prerequisite Concepts

- Python functions and imports.
- Environment variables.
- HTTP server.
- Connection pool.

### Complexity

Medium.

### Final Outcome

You can explain what happens when the backend starts.

### Checkpoint Questions

1. What does `backend/main.py` create?
2. What is the purpose of `Settings` in `backend/config.py`?
3. Why does the backend need a StarRocks connection?
4. Why does it need a NebulaGraph connection?
5. What background job is scheduled on startup?

### Exercise

Trace startup in order: config -> app -> middleware -> routers -> scheduler.

## Phase 4: Diagnoses API

### What You Learn

- How `/api/diagnoses` works.
- How SQL counts become verdicts.
- How backend data becomes frontend table rows.

### Files To Read

1. `backend/routers/diagnoses.py`
2. `backend/services/diagnosis.py`
3. `frontend/src/api.js`
4. `frontend/src/DiagnosesTable.jsx`
5. `docs/code-walkthroughs/backend-diagnoses.md`

### Prerequisite Concepts

- HTTP GET request.
- Query parameter.
- JSON response.
- SQL aggregation.

### Complexity

High.

### Final Outcome

You can trace a diagnoses table refresh from browser to SQL and back.

### Checkpoint Questions

1. What route does the frontend call for diagnoses?
2. Which backend router receives it?
3. Which service computes the verdict?
4. What counts are needed for the verdict?
5. What does the frontend render from the response?

### Exercise

Choose one seeded scenario, such as `BIN-PHANTOM-A`, and trace how it should
appear in the table.

## Phase 5: ETL From StarRocks To NebulaGraph

### What You Learn

- What ETL means.
- Why the graph is derived from SQL rows.
- How the sync job creates graph vertices and edges.

### Files To Read

1. `backend/etl/sync.py`
2. `backend/main.py`
3. `data/schema/nebula.ngql`
4. `docs/code-walkthroughs/etl-sync.md`

### Prerequisite Concepts

- ETL: extract, transform, load.
- Idempotency: safe to run more than once.
- Background scheduler.
- Graph upsert.

### Complexity

High.

### Final Outcome

You can explain how an INF row becomes graph data.

### Checkpoint Questions

1. Where does the ETL read from?
2. Where does the ETL write to?
3. Why is the ETL scheduled every minute?
4. What vertices are created?
5. What edges are created?

### Exercise

Draw the graph created from one failure row:

```text
FSN -> BIN
Picker -> BIN
Order -> BIN
FSN -> GRN -> BIN
```

## Phase 6: Knowledge Graph Signals

### What You Learn

- How graph queries add context beyond SQL counts.
- Picker concentration.
- Shared GRN batch.
- Stocktake feedback.
- ATP proxy.

### Files To Read

1. `backend/services/graph.py`
2. `backend/services/diagnosis.py`
3. `backend/services/agent.py`
4. `docs/deliverables/LLD/04-graph-signals.md`
5. `docs/code-walkthroughs/backend-graph-signals.md`

### Prerequisite Concepts

- Graph traversal.
- Multi-hop relationship.
- Root-cause signal.
- Difference between evidence and verdict.

### Complexity

High.

### Final Outcome

You can explain why the knowledge graph exists and how it improves diagnosis.

### Checkpoint Questions

1. What does picker concentration try to detect?
2. What does shared GRN try to detect?
3. Why can two rows have the same SQL verdict but different graph explanations?
4. Is the graph the source of truth or an enrichment layer?
5. What happens if the graph is unavailable?

### Exercise

Explain this sentence in your own words:

> SQL tells us what pattern happened; graph tells us what relationships may
> explain that pattern.

## Phase 7: LLM Assistant

### What You Learn

- How the assistant receives a question.
- How it calls SQL and graph tools.
- How guardrails reduce bad queries and hallucinations.
- How citations are attached.

### Files To Read

1. `backend/routers/ask.py`
2. `backend/services/agent.py`
3. `backend/services/llm.py`
4. `backend/services/prompts.py`
5. `backend/services/guards.py`
6. `frontend/src/Assistant.jsx`
7. `docs/code-walkthroughs/backend-ask-llm.md`
8. `docs/MIGRATION-TO-OLLAMA.md`

### Prerequisite Concepts

- LLM.
- Prompt.
- Tool calling.
- API client.
- Citation/evidence.
- Timeout.

### Complexity

High.

### Final Outcome

You can trace a user question from UI input to cited answer.

### Checkpoint Questions

1. Which endpoint handles assistant questions?
2. Why does the assistant need tools?
3. What does `guards.py` protect against?
4. Why are citations required?
5. Why is Ollama used through an OpenAI-compatible API?

### Exercise

Trace the question: "Why is BIN-PICKER-A failing?" List what data the assistant
should probably query.

## Phase 8: Feedback Loop

### What You Learn

- How the system tracks recommendations.
- How status moves from suggested to verified.
- How failures before/after are compared.

### Files To Read

1. `backend/routers/feedback.py`
2. `backend/services/feedback.py`
3. `frontend/src/FeedbackView.jsx`
4. `data/schema/starrocks.sql`
5. `docs/code-walkthroughs/backend-feedback.md`

### Prerequisite Concepts

- CRUD operations.
- Status field.
- Audit trail.
- Measuring before and after.

### Complexity

Medium.

### Final Outcome

You can explain the closed loop from diagnosis to action outcome.

### Checkpoint Questions

1. What table stores recommendations?
2. What statuses can a recommendation have?
3. What does `failures_ceased` mean?
4. Why is feedback important for business trust?
5. How does the UI advance a recommendation?

### Exercise

Describe the lifecycle of one recommendation in five steps.

## Phase 9: Frontend

### What You Learn

- How React renders the app.
- How tabs are structured.
- How API calls are made.
- How user actions update the UI.

### Files To Read

1. `frontend/src/main.jsx`
2. `frontend/src/App.jsx`
3. `frontend/src/api.js`
4. `frontend/src/DiagnosesTable.jsx`
5. `frontend/src/Assistant.jsx`
6. `frontend/src/FeedbackView.jsx`
7. `frontend/src/App.css`
8. `frontend/package.json`
9. `frontend/vite.config.js`

### Prerequisite Concepts

- HTML.
- CSS.
- JavaScript.
- React component.
- State.
- Props.
- Event handler.

### Complexity

Medium.

### Final Outcome

You can trace one click from UI to API call to UI update.

### Checkpoint Questions

1. What does `App.jsx` control?
2. What does `api.js` centralize?
3. Which component renders diagnosis rows?
4. Which component renders assistant answers?
5. Which component renders recommendation status?

### Exercise

Trace the "Log Rec" action from button click to feedback row.

## Phase 10: Infrastructure And Running The Project

### What You Learn

- How Docker Compose starts the full stack.
- What ports each service uses.
- How schema initialization works.
- How smoke testing works.

### Files To Read

1. `infra/docker-compose.yml`
2. `infra/Dockerfile.backend`
3. `infra/Dockerfile.frontend`
4. `infra/init_schema.sh`
5. `infra/smoke_test.sh`
6. `README.md`

### Prerequisite Concepts

- Container.
- Image.
- Port.
- Volume.
- Service dependency.
- Health check.

### Complexity

Medium to high.

### Final Outcome

You can start, seed, and smoke-test the full local system.

### Checkpoint Questions

1. What services run in Docker Compose?
2. Which service exposes the frontend?
3. Which service exposes the backend?
4. Which scripts initialize the schema?
5. What does the smoke test verify?

### Exercise

Draw the Docker Compose services and ports.

## Phase 11: Testing, Debugging, Security, And Performance

### What You Learn

- What is tested.
- What is not tested.
- Where failures are likely.
- What is safe or unsafe for production.

### Files To Read

1. `infra/smoke_test.sh`
2. `backend/services/guards.py`
3. `backend/services/agent.py`
4. `backend/services/diagnosis.py`
5. `backend/services/graph.py`
6. `backend/main.py`
7. `docs/deliverables/LLD/09-security.md`
8. `docs/deliverables/HLD/06-quality-attributes.md`

### Prerequisite Concepts

- Unit test.
- Integration test.
- Smoke test.
- Authentication.
- Authorization.
- Injection risk.
- Latency.
- Bottleneck.

### Complexity

High.

### Final Outcome

You can identify real risks and propose improvements.

### Checkpoint Questions

1. Does the repo have full unit tests?
2. What does the smoke test cover?
3. What can go wrong if StarRocks is down?
4. What can go wrong if NebulaGraph is stale?
5. What can go wrong if the LLM hallucinates?

### Exercise

Write five missing tests that would increase confidence in the system.

## Phase 12: Final System Design Defense

### What You Learn

- How to explain the architecture end to end.
- How to defend the tech choices.
- How to propose production improvements.
- How to reason about trade-offs.

### Files To Review

1. `AGENTS.md`
2. `README.md`
3. `design/design-doc.md`
4. `docs/deliverables/HLD/`
5. `docs/deliverables/LLD/`
6. `docs/code-walkthroughs/`
7. All core backend/frontend files studied earlier.

### Prerequisite Concepts

- System design basics.
- Reliability.
- Observability.
- Scalability.
- Maintainability.

### Complexity

High.

### Final Outcome

You can answer:

1. What problem does the system solve?
2. Why does the architecture have these components?
3. Why StarRocks?
4. Why NebulaGraph?
5. Why Ollama?
6. What are the main failure modes?
7. What would you improve before production?

### Final Exercise

Give a 10-minute architecture walkthrough:

```text
problem -> data -> backend -> graph -> LLM -> frontend -> feedback -> risks
```

## Recommended Study Order Summary

| Order | Topic | Main Files | Difficulty |
|---|---|---|---|
| 0 | Orientation | `AGENTS.md`, `README.md` | Low |
| 1 | Domain rules | `design/design-doc.md` | Medium |
| 2 | Data schemas | `data/schema/*` | High |
| 3 | Backend startup | `backend/main.py`, `backend/config.py` | Medium |
| 4 | Diagnoses API | `backend/services/diagnosis.py` | High |
| 5 | ETL | `backend/etl/sync.py` | High |
| 6 | Graph signals | `backend/services/graph.py` | High |
| 7 | LLM assistant | `backend/services/agent.py` | High |
| 8 | Feedback | `backend/services/feedback.py` | Medium |
| 9 | Frontend | `frontend/src/*` | Medium |
| 10 | Infra | `infra/*` | Medium |
| 11 | Quality review | guards, smoke test, security docs | High |
| 12 | Defense | all core docs/code | High |

## What Not To Study First

Avoid starting with these:

- `backend/services/agent.py`
  - It is important but complex. Learn SQL, graph, and APIs first.

- Dockerfiles
  - Useful, but they make more sense after you know what services exist.

- Journal files
  - They are history. Useful later, not the best first learning path.

- CSS details
  - Learn UI behavior before visual styling.

- The PDF briefing
  - Useful context, but the repo docs and code are more directly actionable.

## Running Glossary Topics To Learn

Use [02-glossary.md](02-glossary.md) as you go. Add new terms when something is
unclear. The most important early terms are:

- FSN
- BIN
- INF
- IRT
- phantom inventory
- genuine stockout
- SQL
- graph
- vertex
- edge
- API
- frontend
- backend
- ETL
- LLM
- citation
- Docker
