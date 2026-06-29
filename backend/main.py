import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.db.nebula import init_nebula_pool
from backend.etl.sync import run_etl_sync

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── startup ────────────────────────────────────────────────────────────
    init_nebula_pool()

    scheduler = BackgroundScheduler()
    scheduler.add_job(run_etl_sync, "interval", minutes=1, id="etl_sync")
    scheduler.start()
    logger.info("ETL scheduler started (1-min interval)")

    yield

    # ── shutdown ───────────────────────────────────────────────────────────
    scheduler.shutdown(wait=False)
    logger.info("ETL scheduler stopped")


app = FastAPI(
    title="BIN-FSN Stockout Diagnosis",
    description=(
        "Diagnoses warehouse pick failures (INF events) into PHANTOM vs GENUINE_STOCKOUT "
        "with graph multi-hop signals and a cited LLM assistant."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to the frontend origin before production
    allow_methods=["*"],
    allow_headers=["*"],
)

from backend.routers import diagnoses, ask, feedback
app.include_router(diagnoses.router, prefix="/api", tags=["diagnoses"])
app.include_router(ask.router,       prefix="/api", tags=["assistant"])
app.include_router(feedback.router,  prefix="/api", tags=["feedback"])


@app.get("/health")
def health():
    return {"status": "ok"}
