"""
PostgreSQL connection helper for persistence.
"""

import logging
import os
from typing import Any

import psycopg2
from psycopg2 import extensions

logger = logging.getLogger(__name__)

_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def ensure_schema(db_config: dict[str, Any]) -> None:
    """
    Create tables and indexes if they do not exist (idempotent).
    Run on startup so DB is ready whether or not Postgres init script ran.
    """
    if not os.path.isfile(_SCHEMA_PATH):
        logger.warning("Schema file not found at %s, skipping ensure_schema", _SCHEMA_PATH)
        return
    try:
        with open(_SCHEMA_PATH, encoding="utf-8") as f:
            sql = f.read()
    except OSError as e:
        logger.error("Cannot read schema file: %s", e)
        return
    # Split into statements; drop comment-only lines from each, then skip empty
    statements = []
    for s in sql.split(";"):
        lines = [line for line in s.splitlines() if line.strip() and not line.strip().startswith("--")]
        stmt = " ".join(l for l in lines).strip()
        if stmt:
            statements.append(stmt)
    if not statements:
        return
    try:
        conn = psycopg2.connect(
            host=db_config["host"],
            port=db_config["port"],
            dbname=db_config["database"],
            user=db_config["user"],
            password=db_config["password"],
        )
        conn.autocommit = True
        try:
            with conn.cursor() as cur:
                for stmt in statements:
                    cur.execute(stmt)
            logger.info("Schema ensured (tables/indexes created if missing)")
        finally:
            conn.close()
    except Exception as e:
        logger.error("Schema ensure failed: %s", e)
        raise


def get_connection(db_config: dict[str, Any]) -> extensions.connection:
    """
    Return a new DB connection. Caller must close it.
    Logs ERROR on failure with message.
    """
    try:
        conn = psycopg2.connect(
            host=db_config["host"],
            port=db_config["port"],
            dbname=db_config["database"],
            user=db_config["user"],
            password=db_config["password"],
        )
        conn.autocommit = False
        logger.debug(
            "DB connection opened to %s@%s:%s/%s",
            db_config["user"],
            db_config["host"],
            db_config["port"],
            db_config["database"],
        )
        return conn
    except Exception as e:
        logger.error("DB connection failed: %s", e)
        raise
