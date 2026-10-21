from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.app.domain.employee import Employee
from src.app.domain.employer import Employer
from src.app.domain.employment import Employment
from src.app.infrastructure.database import create_database_engine, create_schema
from src.app.infrastructure.orm_models import EmployeeRow, EmployerRow, EmploymentRow
from src.app.infrastructure.sqlalchemy_setup_repository import SqlAlchemySetupRepository

EMPLOYEE_AHV = "756.9876.5432.10"


def make_employer(**overrides):
    fields = {
        "name": "Anna Muster",
        "address": "Freie Strasse 1, 4001 Basel",
        "ahv_number": "756.1234.5678.97",
        "contact_info": "anna.muster@example.ch",
    }
    return Employer(**{**fields, **overrides})


def make_employee(**overrides):
    fields = {
        "name": "Maria Rossi",
        "address": "Clarastrasse 10, 4058 Basel",
        "ahv_number": EMPLOYEE_AHV,
        "nationality": "Italy",
    }
    return Employee(**{**fields, **overrides})


def make_employment(**overrides):
    fields = {
        "start_date": date(2026, 3, 1),
        "end_date": date(2026, 12, 31),
        "hourly_wage": 28.50,
        "weekly_hours": 6.5,
        "holiday_weeks": 5,
    }
    return Employment(**{**fields, **overrides})


@pytest.fixture
def database_url(tmp_path):
    return f"sqlite:///{tmp_path / 'payroll.db'}"


@pytest.fixture
def engine(database_url):
    engine = create_database_engine(database_url)
    create_schema(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def repository(engine):
    return SqlAlchemySetupRepository(engine)


def count(engine, row):
    with Session(engine) as session:
        return session.scalar(select(func.count()).select_from(row))


def test_get_employer_is_none_before_setup(repository):
    assert repository.get_employer() is None


def test_save_stores_all_three_linked_with_minutes_and_centimes(repository, engine):
    result = repository.save(make_employer(), make_employee(), make_employment())

    with Session(engine) as session:
        row = session.get(EmploymentRow, result.employment_id)
        assert (row.employer_id, row.employee_id) == (result.employer_id, result.employee_id)
        assert row.weekly_minutes == 390
        assert row.hourly_wage_cents == 2850
        assert row.holiday_weeks == 5
        assert (row.start_date, row.end_date) == (date(2026, 3, 1), date(2026, 12, 31))
        assert session.get(EmployeeRow, result.employee_id).name == "Maria Rossi"
        assert session.get(EmployerRow, result.employer_id).name == "Anna Muster"


def test_saved_employer_is_returned_with_its_id(repository):
    result = repository.save(make_employer(), make_employee(), make_employment())

    assert repository.get_employer() == make_employer(id=result.employer_id)


def test_employer_with_an_id_is_only_linked(repository, engine):
    first = repository.save(make_employer(), make_employee(), make_employment())

    second = repository.save(
        repository.get_employer(), make_employee(ahv_number="756.1111.2222.33"), make_employment()
    )

    assert second.employer_id == first.employer_id
    assert count(engine, EmployerRow) == 1


def test_get_employee_finds_the_saved_employee_by_ahv_number(repository):
    result = repository.save(make_employer(), make_employee(), make_employment())

    assert repository.get_employee(EMPLOYEE_AHV) == make_employee(id=result.employee_id)
    assert repository.get_employee("756.1111.2222.33") is None


def test_employee_with_an_id_is_only_linked(repository, engine):
    first = repository.save(make_employer(), make_employee(), make_employment())

    second = repository.save(
        repository.get_employer(), repository.get_employee(EMPLOYEE_AHV), make_employment()
    )

    assert second.employee_id == first.employee_id
    assert second.employment_id != first.employment_id
    assert count(engine, EmployeeRow) == 1
    assert count(engine, EmploymentRow) == 2


def test_get_employment_returns_the_saved_employment_in_hours_and_francs(repository):
    result = repository.save(make_employer(), make_employee(), make_employment())

    employment = repository.get_employment(result.employment_id)

    assert employment == make_employment(
        id=result.employment_id, employer_id=result.employer_id, employee_id=result.employee_id
    )
    assert repository.get_employment(result.employment_id + 1) is None


def test_failed_save_leaves_nothing_saved(repository, engine):
    repository.save(make_employer(), make_employee(), make_employment())

    with pytest.raises(IntegrityError):
        repository.save(
            make_employer(ahv_number="756.2222.3333.44"), make_employee(), make_employment()
        )

    assert count(engine, EmployerRow) == 1
    assert count(engine, EmployeeRow) == 1
    assert count(engine, EmploymentRow) == 1


def test_setup_data_survives_a_restart(database_url, engine):
    result = SqlAlchemySetupRepository(engine).save(make_employer(), make_employee(), make_employment())
    engine.dispose()

    restarted = create_database_engine(database_url)
    try:
        repository = SqlAlchemySetupRepository(restarted)
        assert repository.get_employer().id == result.employer_id
        assert repository.get_employment(result.employment_id).weekly_hours == 6.5
    finally:
        restarted.dispose()
