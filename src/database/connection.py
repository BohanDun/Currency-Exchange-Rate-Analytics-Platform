"""Create and manage PostgreSQL connections."""

from __future__ import annotations

import os
from collections.abc import Mapping

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL


class DatabaseConfigurationError(ValueError):
    """Raised when required database settings are missing or invalid."""


def build_database_url(environment: Mapping[str, str] | None = None) -> URL:
    """Build a PostgreSQL URL without exposing or manually escaping passwords."""
    env = environment if environment is not None else os.environ
    required = ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD")
    missing = [name for name in required if not env.get(name)]
    if missing:
        raise DatabaseConfigurationError(
            f"Missing required database settings: {', '.join(missing)}"
        )

    host = env.get("POSTGRES_HOST", "localhost")
    raw_port = env.get("POSTGRES_PORT", "5432")
    try:
        port = int(raw_port)
    except ValueError as exc:
        raise DatabaseConfigurationError("POSTGRES_PORT must be an integer") from exc
    if not 1 <= port <= 65535:
        raise DatabaseConfigurationError("POSTGRES_PORT must be between 1 and 65535")

    return URL.create(
        drivername="postgresql+psycopg2",
        username=env["POSTGRES_USER"],
        password=env["POSTGRES_PASSWORD"],
        host=host,
        port=port,
        database=env["POSTGRES_DB"],
    )


def create_database_engine(
    environment: Mapping[str, str] | None = None,
    *,
    pool_pre_ping: bool = True,
) -> Engine:
    """Create a reusable SQLAlchemy engine for the configured PostgreSQL server."""
    return create_engine(
        build_database_url(environment),
        pool_pre_ping=pool_pre_ping,
        future=True,
    )
