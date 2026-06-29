"""
backend/db/starrocks.py
=======================
Thin connection factory for StarRocks (MySQL-compatible protocol via PyMySQL).
Returns a connection pool-like singleton using a simple cached connection.
"""

import pymysql
from backend.config import settings


def get_connection() -> pymysql.connections.Connection:
    """Open a new PyMySQL connection to StarRocks on every call.

    Callers are responsible for closing the connection. For the ETL sync and
    API handlers, short-lived per-request connections are fine at demo scale.
    In production, swap this for a connection pool (e.g. DBUtils PooledDB).
    """
    return pymysql.connect(
        host=settings.starrocks_host,
        port=settings.starrocks_port,
        user=settings.starrocks_user,
        password=settings.starrocks_password,
        database=settings.starrocks_database,
        connect_timeout=10,
        cursorclass=pymysql.cursors.DictCursor,
    )
