"""
Database Connection Management
Handles PostgreSQL connections with context manager pattern.
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
import logging

from artcrm.config import config

logger = logging.getLogger(__name__)


@contextmanager
def get_db_connection():
    """
    Context manager for database connections.
    Automatically commits on success, rollbacks on error, and closes connection.

    Usage:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM contacts")
            results = cur.fetchall()
    """
    conn = None
    try:
        conn = psycopg2.connect(config.DATABASE_URL)
        logger.debug("Database connection established")
        yield conn
        conn.commit()
        logger.debug("Transaction committed")
    except Exception as e:
        if conn:
            conn.rollback()
            logger.error(f"Transaction rolled back due to error: {e}")
        raise
    finally:
        if conn:
            conn.close()
            logger.debug("Database connection closed")


@contextmanager
def get_db_cursor(dict_cursor=True):
    """
    Context manager for database cursor.
    Returns RealDictCursor by default for row-as-dict results.

    Usage:
        with get_db_cursor() as cur:
            cur.execute("SELECT * FROM contacts WHERE id = %s", (42,))
            contact = cur.fetchone()  # Returns dict-like object
    """
    with get_db_connection() as conn:
        cursor_factory = RealDictCursor if dict_cursor else None
        cur = conn.cursor(cursor_factory=cursor_factory)
        try:
            yield cur
        finally:
            cur.close()
