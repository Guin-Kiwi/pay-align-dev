from dataclasses import replace

from sqlalchemy.exc import IntegrityError

import pytest
from src.app.domain.errors import DuplicateMonthError, InvalidPayrollInputError
from tests.database_helpers import add_employment, count_rows, empty_postgres_url
from src.app.infrastructure.database import create_database_engine, create_schema
from src.app.infrastructure.sqlalchemy_payroll_repository import (
    SqlAlchemyPayrollRepository,
    _is_unique_violation,
)
from tests.integration.test_sqlalchemy_payroll_repository import make_run


@pytest.fixture(params=["sqlite", "postgresql"])
def repository(request, tmp_path):
    if request.param == "postgresql":
        url = empty_postgres_url()
    else:
        url = f"sqlite:///{tmp_path / 'payroll.db'}"
    engine = create_database_engine(url)
    create_schema(engine)
    add_employment(engine, employment_id=7, employer_id=3, employee_id=9)
    yield SqlAlchemyPayrollRepository(engine)
    engine.dispose()


def test_invalid_category_raises_invalid_payroll_input_and_persists_nothing(repository):
    record, entries, snapshot, payslip = make_run()
    entries = (replace(entries[0], category="holiday"),)

    with pytest.raises(InvalidPayrollInputError):
        repository.save_payroll_run(record, entries, snapshot, payslip)

    assert count_rows(repository.engine, "monthly_records") == 0
    assert count_rows(repository.engine, "work_entries") == 0


def test_same_employment_month_year_twice_still_raises_duplicate_month(repository):
    record, entries, snapshot, payslip = make_run()
    repository.save_payroll_run(record, entries, snapshot, payslip)

    with pytest.raises(DuplicateMonthError):
        repository.save_payroll_run(record, entries, snapshot, payslip)


def test_repository_has_no_count_rows_method(repository):
    assert not hasattr(repository, "count_rows")


def test_port_is_abstract_and_the_adapter_implements_it(repository):
    from src.app.application.ports.payroll_repository import PayrollRepositoryPort

    with pytest.raises(TypeError):
        PayrollRepositoryPort()
    assert isinstance(repository, PayrollRepositoryPort)


def test_a_run_for_an_unknown_employment_is_not_a_duplicate_month(repository):
    record, entries, snapshot, payslip = make_run(employment_id=99)

    with pytest.raises(InvalidPayrollInputError) as raised:
        repository.save_payroll_run(record, entries, snapshot, payslip)

    assert not isinstance(raised.value, DuplicateMonthError)


class _PostgresError(Exception):
    def __init__(self, sqlstate):
        super().__init__("postgres error")
        self.sqlstate = sqlstate


@pytest.mark.parametrize("sqlstate, is_duplicate", [("23505", True), ("23503", False), ("23514", False)])
def test_postgres_errors_are_told_apart_by_their_sqlstate(sqlstate, is_duplicate):
    error = IntegrityError("INSERT", {}, _PostgresError(sqlstate))

    assert _is_unique_violation(error) is is_duplicate
