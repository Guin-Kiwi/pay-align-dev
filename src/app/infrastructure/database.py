import os

from sqlalchemy import Engine, create_engine
from sqlalchemy.pool import StaticPool

from src.app.infrastructure.orm_models import Base

DEFAULT_DATABASE_URL = "sqlite:///:memory:"


def get_database_url() -> str:
    return os.environ.get("DATABASE_URL") or DEFAULT_DATABASE_URL


def create_database_engine(url: str | None = None) -> Engine:
    url = url or get_database_url()
    if not url.startswith("sqlite"):
        return create_engine(url)
    options: dict = {"connect_args": {"check_same_thread": False}}
    if url in ("sqlite://", "sqlite:///:memory:"):
        options["poolclass"] = StaticPool
    return create_engine(url, **options)


def create_schema(engine: Engine) -> None:
    Base.metadata.create_all(engine)
