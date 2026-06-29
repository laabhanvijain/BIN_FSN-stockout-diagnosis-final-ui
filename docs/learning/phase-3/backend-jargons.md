# Backend Jargons

This file explains backend terms used in this project in beginner-friendly
language.

## FastAPI

FastAPI is a Python framework for building APIs.

An API is a set of routes/endpoints that other software can call.

Example route in this project:

```python
@app.get("/health")
def health():
    return {"status": "ok"}
```

Meaning:

```text
When someone sends GET /health,
run the health() function,
return {"status": "ok"}.
```

FastAPI helps define routes like:

```text
GET /health
GET /api/diagnoses
POST /api/ask
GET /api/feedback
```

FastAPI gives the backend:

```text
route definitions
request parsing
response creation
JSON handling
validation with Pydantic
automatic API docs
middleware support
startup/shutdown lifecycle
```

In this project, FastAPI is used in:

```text
backend/main.py
backend/routers/
```

`backend/main.py` creates the app:

```python
app = FastAPI(
    title="BIN-FSN Stockout Diagnosis",
    description="...",
    version="0.1.0",
    lifespan=lifespan,
)
```

That `app` is the backend application object.

Then routers are attached:

```python
app.include_router(diagnoses.router, prefix="/api", tags=["diagnoses"])
app.include_router(ask.router, prefix="/api", tags=["assistant"])
app.include_router(feedback.router, prefix="/api", tags=["feedback"])
```

So FastAPI is responsible for saying:

```text
If request comes to /api/diagnoses, send it to diagnoses router.
If request comes to /api/ask, send it to ask router.
If request comes to /api/feedback, send it to feedback router.
```

## Uvicorn

Uvicorn is the server that runs the FastAPI app.

Your FastAPI code is just Python objects and functions. By itself, it is not
listening on a network port.

Uvicorn does the listening.

It opens a port, receives HTTP requests, passes them to FastAPI, gets the
response, and sends it back to the client.

Example command:

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Meaning:

```text
backend.main = import backend/main.py
app = find the FastAPI app object named app
--host 0.0.0.0 = listen on all network interfaces
--port 8000 = serve backend on port 8000
```

So when the browser/frontend calls:

```text
http://localhost:8000/health
```

Uvicorn receives the request first.

Then it passes it to FastAPI.

FastAPI sees:

```text
GET /health
```

and calls:

```python
health()
```

Then FastAPI returns:

```json
{"status": "ok"}
```

Then Uvicorn sends that response back over HTTP.

## FastAPI Vs Uvicorn

FastAPI and Uvicorn work together, but they are not the same thing.

Restaurant analogy:

```text
FastAPI = the restaurant logic/menu
Uvicorn = the building/front door/waiter that receives customers
```

Web-app analogy:

```text
FastAPI = your Python web application framework
Uvicorn = the server process that runs that application
```

Request flow:

```text
Browser / frontend
  -> HTTP request
  -> Uvicorn receives request on port 8000
  -> Uvicorn passes request to FastAPI app
  -> FastAPI matches route
  -> FastAPI calls Python function/router
  -> function returns data
  -> FastAPI converts to HTTP/JSON response
  -> Uvicorn sends response back
```

Why both are needed:

| Tool | Job |
|---|---|
| FastAPI | Defines API logic: routes, validation, responses, lifecycle |
| Uvicorn | Runs the app as an HTTP server and listens on a port |

FastAPI is not the network server by itself.

Uvicorn is not the business logic framework by itself.

Together:

```text
Uvicorn runs FastAPI.
FastAPI handles API logic.
```

## ASGI

ASGI means:

```text
Asynchronous Server Gateway Interface
```

Beginner meaning:

```text
A standard way for Python web servers and Python web apps to talk to each other.
```

FastAPI is an ASGI application.

Uvicorn is an ASGI server.

So:

```text
Uvicorn knows how to run FastAPI because both speak ASGI.
```

## Middleware

Middleware is code that sits between:

```text
incoming request
  and
your actual route/function
```

and also between:

```text
your route/function response
  and
the final response sent back to the client
```

So middleware can inspect, modify, allow, block, log, or enrich requests and
responses.

Building analogy:

```text
Visitor enters building
  -> security desk checks them
  -> visitor goes to correct office
  -> office gives response
  -> security desk may log exit
  -> visitor leaves
```

Backend request analogy:

```text
Client sends request
  -> middleware runs
  -> FastAPI route runs
  -> middleware may run again on response
  -> response goes back
```

Common middleware jobs:

```text
CORS handling
authentication checks
request logging
response compression
rate limiting
adding security headers
tracking request time
error handling
```

In this project, middleware is added in `backend/main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

The middleware used here is:

```text
CORSMiddleware
```

Its job is to handle browser cross-origin rules.

## CORS

CORS means:

```text
Cross-Origin Resource Sharing
```

It is a browser security rule.

To understand CORS, first understand origin.

An origin is:

```text
protocol + hostname + port
```

Examples:

```text
http://localhost:3000
http://localhost:8000
https://example.com
```

These are different origins:

```text
http://localhost:3000
http://localhost:8000
```

because the ports are different.

In this project:

```text
Frontend runs on http://localhost:3000
Backend runs on http://localhost:8000
```

So from the browser's perspective:

```text
frontend origin != backend origin
```

The browser says:

```text
Before frontend JavaScript can call the backend,
the backend must explicitly allow it.
```

That permission is CORS.

### Why CORS Exists

CORS protects users from malicious websites.

Imagine you are logged into an internal dashboard, and then you open a random
malicious website. Without browser protections, that malicious site could try to
call internal APIs from your browser.

CORS helps stop random websites from reading API responses unless the API
explicitly allows them.

Important:

```text
CORS is enforced by browsers.
CORS is not the same as backend authentication.
```

A command-line tool like `curl` does not care about CORS in the same way a
browser does.

### How CORS Works

When frontend JavaScript calls a backend on another origin, the browser checks
the backend response headers.

The backend must return headers like:

```text
Access-Control-Allow-Origin: http://localhost:3000
```

This tells the browser:

```text
Yes, JavaScript from http://localhost:3000 may read this response.
```

For some requests, especially `POST`, custom headers, or non-simple content
types, the browser first sends a preflight request:

```text
OPTIONS /api/ask
```

It is basically asking:

```text
Backend, is it okay if I later send POST /api/ask with these headers?
```

If the backend responds with correct CORS headers, the browser sends the actual
request.

### CORS In This Project

In `backend/main.py`, the project has:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to the frontend origin before production
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Meaning:

```text
allow_origins=["*"]  -> allow requests from any origin
allow_methods=["*"]  -> allow all HTTP methods
allow_headers=["*"]  -> allow all request headers
```

This is convenient for local demo because the frontend and backend may run on
different ports.

For production, this is too open.

Production should use something like:

```python
allow_origins=[
    "https://stockout-diagnosis.company.com"
]
```

or for local development only:

```python
allow_origins=[
    "http://localhost:3000"
]
```

### CORS Is Not Authentication

CORS answers:

```text
Is this browser origin allowed to call/read this API?
```

Authentication answers:

```text
Who is this user?
```

Authorization answers:

```text
What is this user allowed to access?
```

These are different concerns.

### Request Flow With CORS

Example GET:

```text
React app at http://localhost:3000
  -> wants GET http://localhost:8000/api/diagnoses
  -> browser sees different origin
  -> browser enforces CORS
  -> backend CORSMiddleware adds allow headers
  -> browser allows frontend to read response
```

Example POST:

```text
React app at http://localhost:3000
  -> wants POST http://localhost:8000/api/ask
  -> browser may send OPTIONS preflight first
  -> CORSMiddleware responds with allowed methods/headers
  -> browser sends actual POST
  -> backend route handles /api/ask
```

Memory hook:

```text
Middleware = code that runs around requests and responses.
CORS middleware = middleware that tells browsers which frontend origins may call the backend.
```

For this project:

```text
CORSMiddleware is used so the React frontend can call the FastAPI backend.
allow_origins=["*"] is fine for demo, but should be restricted before production.
```

## Router

A router is a way to group related API endpoints.

In FastAPI, instead of putting every endpoint directly in `main.py`, endpoints
are split into separate router files.

In this project:

```text
backend/routers/diagnoses.py
backend/routers/ask.py
backend/routers/feedback.py
```

Each file owns one area of the API.

Office analogy:

```text
main.py = building reception
diagnoses.py = diagnosis department
ask.py = assistant department
feedback.py = feedback department
```

When a request comes in, `main.py` directs it to the correct router.

### Why Routers Exist

Without routers, `backend/main.py` would contain everything:

```text
health endpoint
diagnoses endpoint
ask endpoint
feedback endpoint
startup logic
CORS
scheduler
database setup
```

That would become messy.

Routers keep code organized:

```text
main.py -> app setup
diagnoses.py -> diagnosis API
ask.py -> assistant API
feedback.py -> feedback API
```

So each file has one clear responsibility.

### How Routers Are Attached

In `backend/main.py`:

```python
from backend.routers import diagnoses, ask, feedback

app.include_router(diagnoses.router, prefix="/api", tags=["diagnoses"])
app.include_router(ask.router,       prefix="/api", tags=["assistant"])
app.include_router(feedback.router,  prefix="/api", tags=["feedback"])
```

Meaning:

```text
Take the router from diagnoses.py and mount it under /api.
Take the router from ask.py and mount it under /api.
Take the router from feedback.py and mount it under /api.
```

So if `diagnoses.py` defines:

```text
/diagnoses
```

then after mounting with prefix `/api`, the full route becomes:

```text
/api/diagnoses
```

### What `prefix="/api"` Means

Prefix means:

```text
Add this in front of every route inside this router.
```

Example:

```python
app.include_router(diagnoses.router, prefix="/api")
```

If the router has:

```python
@router.get("/diagnoses")
```

Final route:

```text
GET /api/diagnoses
```

If the feedback router has:

```python
@router.get("/feedback")
@router.post("/feedback")
@router.patch("/feedback/{id}/status")
```

Final routes become:

```text
GET   /api/feedback
POST  /api/feedback
PATCH /api/feedback/{id}/status
```

### What `tags=["diagnoses"]` Means

Tags are mostly for documentation.

FastAPI automatically generates API docs. Tags group routes visually in those
docs.

Example:

```python
tags=["diagnoses"]
```

Meaning:

```text
Show these endpoints under the diagnoses section in API docs.
```

Tags do not change business logic.

### What A Router File Usually Looks Like

A typical FastAPI router file looks like:

```python
from fastapi import APIRouter

router = APIRouter()

@router.get("/diagnoses")
def diagnoses_endpoint():
    return [...]
```

Important pieces:

```python
router = APIRouter()
```

This creates the router object.

```python
@router.get("/diagnoses")
```

This says:

```text
When a GET request comes to /diagnoses, call the function below.
```

```python
def diagnoses_endpoint():
```

This function handles the request.

### Request Flow With Router

Example request:

```text
GET /api/diagnoses
```

Flow:

```text
Frontend sends GET /api/diagnoses
  -> Uvicorn receives request
  -> FastAPI app sees /api prefix
  -> FastAPI finds diagnoses router
  -> diagnoses router matches /diagnoses
  -> diagnoses endpoint function runs
  -> endpoint calls service logic
  -> service queries StarRocks
  -> response returns
```

### Router Vs Service

Router:

```text
HTTP layer
```

Service:

```text
business logic layer
```

Router's usual job:

```text
receive HTTP request
validate request parameters/body
call service function
return response
```

Business logic usually belongs in:

```text
backend/services/
```

Example:

```text
backend/routers/diagnoses.py
  -> receives GET /api/diagnoses
  -> reads query parameters
  -> calls backend/services/diagnosis.py

backend/services/diagnosis.py
  -> builds SQL
  -> queries StarRocks
  -> computes diagnosis rows
```

Memory hook:

```text
main.py = starts the backend and connects routers
router = maps URL + HTTP method to Python function
service = performs the actual business logic
```

For this project:

```text
GET /api/diagnoses
  -> diagnoses router
  -> diagnosis service
  -> StarRocks
  -> JSON response
```

## In This Project

The dependency file:

```text
backend/requirements.txt
```

contains:

```text
fastapi==0.111.0
uvicorn[standard]==0.29.0
```

`fastapi` is used to build the backend API.

`uvicorn` is used to run it.

In Docker, the backend container runs Uvicorn to serve:

```text
backend.main:app
```

Meaning:

```text
Use the app object from backend/main.py.
```

## Tiny Example

Imagine this code:

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/hello")
def hello():
    return {"message": "hi"}
```

This defines the API, but it is not running yet.

To run it:

```bash
uvicorn myfile:app --port 8000
```

Then a browser can call:

```text
http://localhost:8000/hello
```

Response:

```json
{"message": "hi"}
```

## Memory Hook

```text
FastAPI = what routes exist and what they do
Uvicorn = starts the server and receives requests
```

For this project:

```text
FastAPI defines /health, /api/diagnoses, /api/ask, /api/feedback.
Uvicorn runs that FastAPI app on port 8000.
```
