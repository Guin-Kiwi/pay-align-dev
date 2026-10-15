import pytest
from sqlalchemy import inspect, text

from src.app.infrastructure.database import (
    DatabaseConfigurationError,
    create_database_engine,
    create_schema,
    get_database_url,
)

ENTITY_TABLES = {"employers", "employees", "employments", "monthly_records", "payslips"}


def test_database_url_is_read_from_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:////app/data/payroll.db")
    assert get_database_url() == "sqlite:////app/data/payroll.db"


@pytest.fixture
def engines():
    created = []

    def make(url):
        engine = create_database_engine(url)
        created.append(engine)
        return engine

    yield make
    for engine in created:
        engine.dispose()


@pytest.mark.parametrize("value", [None, "", "   "])
def test_unset_or_blank_database_url_is_rejected(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("DATABASE_URL", value)
    with pytest.raises(DatabaseConfigurationError, match="DATABASE_URL"):
        get_database_url()


@pytest.mark.parametrize(
    "url", ["postgresql://user:pw@host/db", "mysql://host/db", "not a url", "payroll.db"]
)
def test_unsupported_or_malformed_database_url_is_rejected(url):
    with pytest.raises(DatabaseConfigurationError, match="DATABASE_URL"):
        create_database_engine(url)


def test_create_database_engine_reads_the_environment_when_no_url_is_given(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'payroll.db'}")
    engine = create_database_engine()
    try:
        assert engine.url.database == str(tmp_path / "payroll.db")
    finally:
        engine.dispose()


def test_create_database_engine_without_any_url_is_rejected(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(DatabaseConfigurationError, match="DATABASE_URL"):
        create_database_engine()


@pytest.mark.parametrize("url", ["sqlite://", "sqlite:///:memory:"])
def test_in_memory_url_shares_one_database_across_connections(url, engines):
    engine = engines(url)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE t (id INTEGER)"))
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM t")).scalar() == 0


def test_file_url_that_merely_contains_memory_is_not_treated_as_in_memory(tmp_path, engines):
    engine = engines(f"sqlite:///{tmp_path / 'memory.db'}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE t (id INTEGER)"))
    assert (tmp_path / "memory.db").exists()


def test_create_schema_creates_skeleton_tables_for_the_five_entities(tmp_path, engines):
    engine = engines(f"sqlite:///{tmp_path / 'payroll.db'}")
    create_schema(engine)
    assert set(inspect(engine).get_table_names()) == ENTITY_TABLES


def test_create_schema_preserves_foreign_key_relationships(tmp_path):
    engine = create_database_engine(f"sqlite:///{tmp_path / 'payroll.db'}")
    create_schema(engine)
    inspector = inspect(engine)

    def references(table):
        return {
            (tuple(fk["constrained_columns"]), fk["referred_table"])
            for fk in inspector.get_foreign_keys(table)
        }

    assert references("employments") == {
        (("employer_id",), "employers"),
        (("employee_id",), "employees"),
    }
    assert references("monthly_records") == {
        (("employment_id",), "employments"),
        (("employer_id",), "employers"),
    }
    assert references("payslips") == {(("monthly_record_id",), "monthly_records")}


def test_monthly_records_hold_the_documented_fields(tmp_path, engines):
    engine = engines(f"sqlite:///{tmp_path / 'payroll.db'}")
    create_schema(engine)
    columns = {c["name"] for c in inspect(engine).get_columns("monthly_records")}
    assert columns == {
        "id", "employment_id", "employer_id", "month", "year",
        "hours_worked", "holiday_hours", "public_holiday_hours",
        "cash_bonus_cents", "expense_reimbursements_cents",
    }


def test_create_schema_is_idempotent(tmp_path):
    engine = create_database_engine(f"sqlite:///{tmp_path / 'payroll.db'}")
    create_schema(engine)
    create_schema(engine)
    assert set(inspect(engine).get_table_names()) == ENTITY_TABLES


def test_schema_persists_in_the_file_named_by_the_url(tmp_path):
    url = f"sqlite:///{tmp_path / 'payroll.db'}"
    create_schema(create_database_engine(url))
    assert set(inspect(create_database_engine(url)).get_table_names()) == ENTITY_TABLES
