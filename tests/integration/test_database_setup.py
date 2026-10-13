import sqlite3

from sqlalchemy import inspect

from src.app.domain.monthly_record import MonthlyRecord
from src.app.domain.payslip import Payslip
from src.app.infrastructure.database import (
    create_database_engine,
    create_schema,
    get_database_url,
)
from src.app.infrastructure.sqlite_payroll_repository import SQLitePayrollRepository

ENTITY_TABLES = {"employers", "employees", "employments", "monthly_records", "payslips"}


def test_database_url_is_read_from_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:////app/data/payroll.db")
    assert get_database_url() == "sqlite:////app/data/payroll.db"


def test_database_url_defaults_to_in_memory_sqlite(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert get_database_url() == "sqlite:///:memory:"


def test_create_schema_creates_skeleton_tables_for_the_five_entities(tmp_path):
    engine = create_database_engine(f"sqlite:///{tmp_path / 'payroll.db'}")
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


def test_create_schema_is_idempotent(tmp_path):
    engine = create_database_engine(f"sqlite:///{tmp_path / 'payroll.db'}")
    create_schema(engine)
    create_schema(engine)
    assert set(inspect(engine).get_table_names()) == ENTITY_TABLES


def test_schema_persists_in_the_file_named_by_the_url(tmp_path):
    url = f"sqlite:///{tmp_path / 'payroll.db'}"
    create_schema(create_database_engine(url))
    assert set(inspect(create_database_engine(url)).get_table_names()) == ENTITY_TABLES


def test_payroll_repository_saves_a_run_into_the_created_schema(tmp_path):
    engine = create_database_engine(f"sqlite:///{tmp_path / 'payroll.db'}")
    create_schema(engine)
    repository = SQLitePayrollRepository(engine.raw_connection().driver_connection)

    record, payslip = repository.save_payroll_run(
        MonthlyRecord(employment_id=1, month=10, year=2026, hours_worked=10),
        Payslip(gross_wage=250.01, net_payout=200.0),
        employer_id=1,
    )

    assert repository.get_monthly_record(record.id).hours_worked == 10
    assert repository.get_payslip(record.id).gross_wage == 250.01


def test_in_memory_engine_exposes_the_driver_connection():
    engine = create_database_engine("sqlite:///:memory:")
    create_schema(engine)
    connection = engine.raw_connection().driver_connection
    assert isinstance(connection, sqlite3.Connection)
    assert set(inspect(engine).get_table_names()) == ENTITY_TABLES
