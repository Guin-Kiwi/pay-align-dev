from dataclasses import replace

import pytest
from src.app.domain.errors import DuplicateMonthError, InvalidPayrollInputError
from tests.db_helpers import count_rows
from src.app.infrastructure.database import create_database_engine, create_schema
from src.app.infrastructure.sqlalchemy_payroll_repository import (
    SqlAlchemyPayrollRepository,
)
from tests.integration.test_sqlalchemy_payroll_repository import make_run


@pytest.fixture
def repository(tmp_path):
    engine = create_database_engine(f"sqlite:///{tmp_path / 'payroll.db'}")
    create_schema(engine)
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
