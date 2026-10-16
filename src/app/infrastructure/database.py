import os

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.pool import StaticPool

from src.app.infrastructure.orm_models import Base

SUPPORTED_BACKENDS = ("sqlite",)


class DatabaseConfigurationError(RuntimeError):
    """Raised when DATABASE_URL is missing, malformed or unsupported."""


def get_database_url() -> str:
    url = (os.environ.get("DATABASE_URL") or "").strip()
    if not url:
        raise DatabaseConfigurationError(
            "DATABASE_URL is not set. Set it to a SQLAlchemy URL, "
            "e.g. sqlite:////app/data/payroll.db."
        )
    return url


def _parse_url(url: str) -> URL:
    try:
        parsed = make_url(url)
    except ArgumentError as error:
        raise DatabaseConfigurationError(
            f"DATABASE_URL is not a valid SQLAlchemy URL: {error}"
        ) from error
    if parsed.get_backend_name() not in SUPPORTED_BACKENDS:
        raise DatabaseConfigurationError(
            f"DATABASE_URL scheme '{parsed.get_backend_name()}' is not supported; "
            f"use one of: {', '.join(SUPPORTED_BACKENDS)}."
        )
    return parsed


def _is_in_memory(url: URL) -> bool:
    return url.database in (None, "", ":memory:")


def create_database_engine(url: str | None = None) -> Engine:
    parsed = _parse_url(url if url is not None else get_database_url())
    options: dict = {"connect_args": {"check_same_thread": False}}
    if _is_in_memory(parsed):
        options["poolclass"] = StaticPool
    return create_engine(parsed, **options)


def create_schema(engine: Engine) -> None:
    Base.metadata.create_all(engine)
