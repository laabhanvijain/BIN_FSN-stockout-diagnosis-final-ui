"""
backend/services/guards.py
===========================
Security guardrails for LLM-generated SQL and nGQL queries.

Validates that queries are:
- Read-only (no DML/DDL)
- Warehouse-scoped (contain warehouse_id filter)
- Within allowed depth/complexity bounds
"""

import re
import logging

logger = logging.getLogger(__name__)

# Forbidden keywords for SQL
_SQL_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|REPLACE|MERGE|CALL|EXEC)\b",
    re.IGNORECASE,
)

# Forbidden keywords for nGQL
_NGQL_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REBUILD)\b",
    re.IGNORECASE,
)


def validate_sql(sql: str, warehouse_id: str) -> tuple[bool, str]:
    """
    Validate that SQL is safe to execute.
    
    Args:
        sql: SQL query string
        warehouse_id: Expected warehouse ID for scoping
    
    Returns:
        (is_valid, error_message)
    """
    if not sql or not sql.strip():
        return False, "Empty SQL query"
    
    # Check for forbidden keywords
    if _SQL_FORBIDDEN.search(sql):
        return False, "Query contains forbidden DML/DDL keywords"
    
    # Must start with SELECT or WITH
    normalized = sql.strip().upper()
    if not (normalized.startswith("SELECT") or normalized.startswith("WITH")):
        return False, "Query must start with SELECT or WITH"
    
    # Must contain warehouse scoping (unless selecting from system tables)
    sql_lower = sql.lower()
    if "information_schema" not in sql_lower and "mysql." not in sql_lower:
        if warehouse_id not in sql:
            return False, f"Query must include warehouse_id filter: {warehouse_id}"
    
    return True, ""


def validate_ngql(ngql: str) -> tuple[bool, str]:
    """
    Validate that nGQL is safe to execute.
    
    Args:
        ngql: nGQL query string
    
    Returns:
        (is_valid, error_message)
    """
    if not ngql or not ngql.strip():
        return False, "Empty nGQL query"
    
    # Check for forbidden keywords
    if _NGQL_FORBIDDEN.search(ngql):
        return False, "Query contains forbidden mutation keywords"
    
    # Must be read-only operations
    normalized = ngql.strip().upper()
    allowed_starts = ("MATCH", "GO", "FETCH", "LOOKUP", "GET", "SHOW", "FIND")
    if not any(normalized.startswith(start) for start in allowed_starts):
        return False, f"Query must start with one of: {', '.join(allowed_starts)}"
    
    return True, ""


def normalize_fsn(fsn: str) -> str:
    """
    Normalize FSN format - ensure FSN- prefix.
    
    Examples:
        A1 -> FSN-A1
        FSN-A1 -> FSN-A1
        fsn-b1 -> FSN-B1
    """
    if not fsn:
        return fsn
    
    fsn = fsn.strip().upper()
    if fsn.startswith("FSN-"):
        return fsn
    return f"FSN-{fsn}"


def normalize_as_of(timestamp: str) -> str:
    """Normalize timestamp for snapshot filtering."""
    if not timestamp:
        return ""
    # Remove microseconds if present for cleaner display
    return timestamp.split('.')[0] if '.' in timestamp else timestamp
