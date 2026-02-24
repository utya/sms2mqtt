"""
PostgreSQL connection helper for persistence.
"""
import logging
from typing import Any

import psycopg2
from psycopg2 import extensions

logger = logging.getLogger(__name__)


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
        logger.debug("DB connection opened to %s@%s:%s/%s", db_config["user"], db_config["host"], db_config["port"], db_config["database"])
        return conn
    except Exception as e:
        logger.error("DB connection failed: %s", e)
        raise
