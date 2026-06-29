# Glossary

This glossary explains project and tech terms in beginner-friendly language.

## Warehouse And Business Terms

| Term | Meaning |
|---|---|
| BIN | A physical warehouse location, shelf, slot, or storage position. |
| FSN | A product/item identifier. It answers: which item are we talking about? |
| INF | Item Not Found. A picker was told to pick an item but could not find it. |
| IRT | Inventory Resolution Ticket. A ticket raised to investigate inventory issues. |
| Picker | Warehouse worker/system actor assigned to pick items. |
| Picklist | A list of items/locations assigned for picking. |
| Warehouse ID | Identifier for the store/dark-store/warehouse. |
| GRN | Goods Receipt Note. In this project, it acts like an inbound batch ID. |
| ATP | Available To Promise. Inventory that can be promised to customers. |
| Fill rate | How often customer demand is successfully fulfilled. |
| Stocktake | Physical counting/checking of inventory in a BIN. |
| Replenish | Add more stock of an FSN. |

## Diagnosis Terms

| Term | Meaning |
|---|---|
| Verdict | The root-cause label assigned by the system. |
| PHANTOM_INVENTORY | Many different FSNs fail in the same BIN. The bin may be wrong/missing/misplaced. |
| GENUINE_STOCKOUT | The same FSN fails across many BINs. The item may truly be depleted. |
| DUAL | Both phantom and stockout patterns appear together. |
| AMBIGUOUS | Not enough evidence to confidently classify. |
| Evidence | Data used to justify a verdict or assistant claim. |
| Citation | A reference to the SQL or graph result behind a claim. |
| Graph signal | A relationship-based clue, such as same picker or same GRN. |

## Tech Stack Terms

| Term | Meaning |
|---|---|
| Frontend | The part users see in the browser. This project uses React. |
| Backend | The server that receives API requests, runs logic, and talks to databases. |
| API | A defined way for frontend and backend to talk, usually over HTTP. |
| HTTP | Protocol browsers use to talk to servers. |
| JSON | A common data format used in API requests/responses. |
| React | JavaScript library for building user interfaces. |
| Component | A reusable piece of React UI. |
| State | Data a React component remembers while the app is running. |
| Props | Data passed from one React component to another. |
| Vite | Tool that runs/builds the frontend app. |
| Axios | JavaScript library for making HTTP requests. |
| Python | Programming language used for backend and data scripts. |
| FastAPI | Python framework for building APIs. |
| Pydantic | Python library for validating settings and request/response data. |
| Uvicorn | Server that runs the FastAPI app. |
| StarRocks | Analytics database used for SQL aggregation. |
| SQL | Query language for relational/table databases. |
| PyMySQL | Python library used to connect to StarRocks via MySQL protocol. |
| NebulaGraph | Graph database used for relationship queries. |
| nGQL | Query language for NebulaGraph. |
| Vertex | A graph node, such as an FSN, BIN, Picker, Order, or GRN. |
| Edge | A relationship between graph vertices. |
| ETL | Extract, Transform, Load: move/reshape data from one system to another. |
| APScheduler | Python scheduler used to run ETL every minute. |
| LLM | Large Language Model, used for natural-language assistant answers. |
| Ollama | Local tool/runtime for running LLMs. |
| OpenAI-compatible API | An API shape that the OpenAI SDK can call, even when the server is Ollama. |
| Docker | Tool for running applications in containers. |
| Docker Compose | Tool for starting multiple containers together. |
| Container | Packaged runtime environment for a service. |
| Health check | A test that tells Docker whether a service is ready. |
| Smoke test | A quick test that verifies the most important system paths work. |

## Code Organization Terms

| Term | Meaning |
|---|---|
| Router | Backend file that defines API endpoints. |
| Service | Backend file that contains business logic. |
| DB client | Code responsible for connecting to a database. |
| Schema | Definition of tables, graph tags, edges, and fields. |
| Migration/DDL | SQL or graph commands that create/update schema. |
| Config | Runtime settings such as hostnames, ports, model name, and timeouts. |
| Dependency | External library the project uses. |
| Package manifest | File listing dependencies, such as `requirements.txt` or `package.json`. |

## Project-Specific File Roles

| File | Role |
|---|---|
| `AGENTS.md` | Project source of truth and status. |
| `README.md` | Main quick-start and overview. |
| `backend/main.py` | Backend application entry point. |
| `backend/config.py` | Environment/config settings. |
| `backend/services/diagnosis.py` | Main deterministic verdict logic. |
| `backend/services/graph.py` | Graph signal queries. |
| `backend/services/agent.py` | LLM assistant tool loop and fallbacks. |
| `backend/etl/sync.py` | StarRocks to NebulaGraph sync. |
| `frontend/src/App.jsx` | Main frontend shell. |
| `frontend/src/api.js` | Frontend API client. |
| `infra/docker-compose.yml` | Full local stack definition. |
| `data/schema/starrocks.sql` | StarRocks tables. |
| `data/schema/nebula.ngql` | NebulaGraph schema. |
