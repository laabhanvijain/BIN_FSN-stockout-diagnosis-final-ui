# Phase 0 Prerequisites

This file explains the basic technical ideas needed before studying the project
code. It assumes you are new to the tech stack.

## What Is A Web App?

A web app is software you use through a browser.

Examples:

- Gmail
- Flipkart
- Google Docs
- An internal warehouse dashboard

A web app usually has two big parts:

```text
Browser screen you see
  +
Server/database behind the scenes
```

In this project:

```text
Browser screen = React frontend
Server = FastAPI backend
Databases = StarRocks + NebulaGraph
LLM = Ollama assistant
```

When you open `http://localhost:3000`, you are opening the frontend.

The frontend does not contain all the warehouse data. It asks the backend for
data.

## What Is A Frontend?

The frontend is the part the user sees and clicks.

In this repo, the frontend lives here:

```text
frontend/src/
```

Important frontend files:

```text
frontend/src/App.jsx
frontend/src/DiagnosesTable.jsx
frontend/src/Assistant.jsx
frontend/src/FeedbackView.jsx
frontend/src/api.js
```

Think of the frontend as the "shop counter."

The user comes to the counter and asks:

- Show me diagnosis rows.
- Why is this BIN failing?
- Log this recommendation.
- Show feedback status.

But the counter does not manufacture the answer itself. It sends requests to the
backend.

## What Is A Backend?

The backend is the server-side part of the application.

It receives requests from the frontend, runs logic, talks to databases, and
returns results.

In this repo, the backend lives here:

```text
backend/
```

Important backend files:

```text
backend/main.py
backend/routers/
backend/services/
backend/db/
backend/etl/
```

Think of the backend as the "operations room."

The frontend asks:

```text
"Give me diagnoses for warehouse WH-BLR-001."
```

The backend then:

```text
Receives request
  -> queries StarRocks
  -> computes verdicts
  -> maybe checks graph signals
  -> returns JSON to frontend
```

## What Is A Database?

A database stores data.

This project uses two kinds of databases:

1. StarRocks
2. NebulaGraph

## What Is StarRocks?

StarRocks is a table/SQL database.

It stores rows like:

```text
warehouse_id | bin_label | fsn  | picker | order_id | updated_at
WH-BLR-001   | BIN-A     | FSN1 | PKR-1  | ORD-1    | 2026-06-29
WH-BLR-001   | BIN-A     | FSN2 | PKR-2  | ORD-2    | 2026-06-29
```

StarRocks is good at counting and grouping.

Example question:

```text
How many different FSNs failed in this BIN?
```

That is a SQL-style question.

## What Is NebulaGraph?

NebulaGraph is a graph database.

Instead of thinking only in rows, it thinks in relationships.

Example:

```text
Picker PKR-1 -> assigned to -> BIN-A
FSN1 -> failed at -> BIN-A
FSN1 -> received in -> GRN-999
GRN-999 -> put away to -> BIN-A
```

NebulaGraph is useful when asking relationship-style questions:

```text
Are many failures connected to the same picker?
Are failed FSNs connected to the same inbound batch?
```

## What Is An API?

API means a defined way for two pieces of software to talk.

Here, the frontend talks to the backend through API routes.

Examples:

```text
GET  /api/diagnoses
POST /api/ask
GET  /api/feedback
POST /api/feedback
```

Simple mental model:

```text
Frontend: "Backend, please give me diagnoses."
Backend: "Sure. Here is JSON data."
```

The frontend code that sends these requests is:

```text
frontend/src/api.js
```

The backend files that receive these requests are in:

```text
backend/routers/
```

## What Is JSON?

JSON is a data format used by APIs.

It looks like this:

```json
{
  "warehouse_id": "WH-BLR-001",
  "bin": "BIN-PHANTOM-A",
  "fsn": "FSN-S1-001",
  "verdict": "PHANTOM_INVENTORY",
  "distinct_fsns": 5,
  "distinct_bins": 1
}
```

The backend sends JSON. The frontend reads JSON and displays it as UI.

## What Is An LLM?

An LLM, or Large Language Model, is a model that can understand and generate
natural language.

In this project, the LLM is used for the assistant tab. The user can ask a
question like:

```text
Why is BIN-PICKER-A failing?
```

The assistant should not invent warehouse facts. It should use tool results from
StarRocks and NebulaGraph, then cite the evidence behind its claims.

This project uses Ollama as the local LLM runtime.

## What Is Docker?

Docker is a tool for running applications in containers.

A container is a packaged environment that includes the things a service needs
to run.

This project has many services:

- StarRocks
- NebulaGraph
- FastAPI backend
- React frontend

Docker Compose starts those services together using:

```text
infra/docker-compose.yml
```

## Phase 0 Mental Model

At the beginner level, think of the system like this:

```text
React frontend
  -> asks backend for data

FastAPI backend
  -> computes business logic
  -> queries databases
  -> calls LLM assistant tools

StarRocks
  -> stores table data
  -> answers counting/grouping questions

NebulaGraph
  -> stores relationships
  -> answers relationship questions

Ollama
  -> generates assistant explanations
  -> should rely on cited data
```

Before moving to code, you should be comfortable with these ideas:

- frontend
- backend
- database
- API
- JSON
- SQL/table data
- graph/relationship data
- LLM
- Docker
