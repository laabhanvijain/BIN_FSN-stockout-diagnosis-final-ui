"""
backend/db/nebula.py
====================
NebulaGraph session factory.

NebulaGraph 3.x uses a connection-pool model. We create one pool at startup
(via init_nebula_pool) and hand out sessions on demand (via get_session).
The pool is stored as a module-level singleton so it is shared across requests
and the ETL scheduler without re-connecting every call.
"""

import logging
from contextlib import contextmanager

from nebula3.Config import Config as NebulaConfig
from nebula3.gclient.net import ConnectionPool

from backend.config import settings

logger = logging.getLogger(__name__)

_pool: ConnectionPool | None = None


def init_nebula_pool() -> None:
    """Initialise the NebulaGraph connection pool.

    Called once at FastAPI startup. Safe to call multiple times — if the pool
    is already initialised it is left untouched.
    """
    global _pool
    if _pool is not None:
        return

    config = NebulaConfig()
    config.max_connection_pool_size = 10

    pool = ConnectionPool()
    ok = pool.init(
        [(settings.nebula_host, settings.nebula_port)],
        config,
    )
    if not ok:
        logger.error("Failed to initialise NebulaGraph connection pool")
        return

    _pool = pool
    logger.info(
        "NebulaGraph pool ready (%s:%s)", settings.nebula_host, settings.nebula_port
    )


@contextmanager
def get_session():
    """Context manager that yields a NebulaGraph session.

    Usage::

        with get_session() as session:
            result = session.execute("USE stockout; MATCH ...")

    Yields None if the pool is not initialised (graph unavailable). Callers
    must check for None before using the session.
    """
    if _pool is None:
        logger.warning("NebulaGraph pool not initialised; skipping graph call")
        yield None
        return

    session = _pool.get_session(settings.nebula_user, settings.nebula_password)
    try:
        yield session
    finally:
        session.release()
