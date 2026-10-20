from dataclasses import FrozenInstanceError, replace
from datetime import date, time

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.app.application.ports.payroll_repository import (
    EmploymentTerms,
    RunSnapshot,
    StoredEmployment,
)
from src.app.domain.hour_categories import MinuteTotals
from src.app.domain.errors import (
    DuplicateMonthError,
    ImmutableRecordError,
    InvalidHolidayBalanceError,
)
from src.app.infrastructure.database import create_database_engine, create_schema
from src.app.infrastructure.orm_models import PayrollSnapshotRow, WorkEntryRow
from tests.database_helpers import add_employment
from src.app.infrastructure.sqlalchemy_payroll_repository import (
    MonthlyRecordInput,
    PayslipInput,
    SqlAlchemyPayrollRepository,
    WorkEntryInput,
)


@pytest.fixture
def repository(tmp_path):
    engine = create_database_engine(f"sqlite:///{tmp_path / 'payroll.db'}")
    create_schema(engine)
    add_employment(engine, employment_id=7, employer_id=3, employee_id=9)
    add_employment(engine, employment_id=8, employer_id=3, employee_id=9)
    yield SqlAlchemyPayrollRepository(engine)
    engine.dispose()


def make_run(*, employment_id=7, employee_id=9, employer_id=3, month=10, year=2026):
    record = MonthlyRecordInput(
        employment_id=employment_id,
        employee_id=employee_id,
        employer_id=employer_id,
        month=month,
        year=year,
        cash_bonus_cents=1234,
        expense_reimbursements_cents=123,
    )
    entries = (
        WorkEntryInput(
            work_date=date(year, month, 14),
            category="worked",
            start_time=time(9),
            end_time=time(13),
            unpaid_break_minutes=15,
            paid_minutes=225,
        ),
    )
    snapshot = RunSnapshot(
        employment=EmploymentTerms(
            hourly_wage_cents=2500,
            weekly_minutes=600,
            holiday_weeks=4,
            employment_start_date=date(2026, 1, 1),
            employment_end_date=date(2026, 12, 15),
        ),
        ruleset_version="2026",
        hours=MinuteTotals(worked=225),
        holiday_balance_minutes=1200,
    )
    payslip = PayslipInput(
        gross_wage_cents=25000,
        ahv_deduction_cents=1325,
        alv_deduction_cents=275,
        tax_deduction_cents=1250,
        nbu_deduction_cents=0,
        net_payout_cents=22274,
        employer_ahv_cents=1325,
        employer_alv_cents=275,
        employer_fak_cents=413,
        employer_bu_cents=126,
        admin_charge_cents=66,
        total_employer_cost_cents=27206,
    )
    return record, entries, snapshot, payslip


def test_saves_explicit_run_inputs_atomically(repository):
    record, entries, snapshot, payslip = make_run()

    saved = repository.save_payroll_run(record, entries, snapshot, payslip)

    assert saved.monthly_record_id == 1
    assert repository.employee_gross_to_date(employee_id=9, year=2026) == 25000
    assert repository.employer_gross_to_date(employer_id=3, year=2026) == 25000


def test_duplicate_month_raises_domain_error_and_keeps_one_run(repository):
    values = make_run()
    repository.save_payroll_run(*values)

    with pytest.raises(DuplicateMonthError):
        repository.save_payroll_run(*make_run())

    assert repository.count_rows("monthly_records") == 1
    assert repository.count_rows("work_entries") == 1
    assert repository.count_rows("payroll_snapshots") == 1
    assert repository.count_rows("payslips") == 1


def test_snapshot_is_unique_per_monthly_record(repository):
    values = make_run()
    repository.save_payroll_run(*values)
    record, entries, snapshot, payslip = values

    with pytest.raises(DuplicateMonthError):
        repository.save_snapshot(record_id=1, snapshot=snapshot)


def test_employee_limit_sums_across_employments(repository):
    repository.save_payroll_run(*make_run(employment_id=7, month=10))
    repository.save_payroll_run(
        *make_run(employment_id=8, month=11, employee_id=9)
    )

    assert repository.employee_gross_to_date(employee_id=9, year=2026) == 50000


def test_employer_limit_sums_across_employments(repository):
    repository.save_payroll_run(*make_run(employment_id=7, month=10, employer_id=3))
    repository.save_payroll_run(
        *make_run(employment_id=8, month=11, employer_id=3)
    )

    assert repository.employer_gross_to_date(employer_id=3, year=2026) == 50000


def test_prior_run_is_read_across_years(repository):
    repository.save_payroll_run(*make_run(year=2025, month=12))

    prior = repository.prior_run(employment_id=7)

    assert prior is not None
    assert prior.year == 2025
    assert prior.holiday_balance_minutes == 1200


def test_invalid_holiday_balance_rolls_back_everything(repository):
    record, entries, snapshot, payslip = make_run()
    invalid_snapshot = replace(snapshot, holiday_balance_minutes=-1)

    with pytest.raises(InvalidHolidayBalanceError):
        repository.save_payroll_run(record, entries, invalid_snapshot, payslip)

    for table in ("monthly_records", "work_entries", "payroll_snapshots", "payslips"):
        assert repository.count_rows(table) == 0


def test_saved_rows_keep_the_agreed_category_names(repository):
    record, entries, snapshot, payslip = make_run()
    repository.save_payroll_run(record, entries, snapshot, payslip)

    with repository.engine.connect() as connection:
        categories = connection.execute(
            text("SELECT category FROM work_entries")
        ).scalars().all()

    assert categories == ["worked"]


def test_every_agreed_category_is_accepted_by_the_constraint(repository):
    record, _, snapshot, payslip = make_run()
    categories = (
        "worked",
        "public_holiday_worked",
        "annual_holiday_taken",
        "public_holiday_taken",
    )
    entries = tuple(
        WorkEntryInput(
            work_date=date(2026, 10, 14),
            category=category,
            start_time=None,
            end_time=None,
            unpaid_break_minutes=0,
            paid_minutes=60,
        )
        for category in categories
    )

    repository.save_payroll_run(record, entries, snapshot, payslip)

    assert repository.count_rows("work_entries") == 4


def test_unknown_category_is_rejected_by_the_constraint(repository):
    record, _, snapshot, payslip = make_run()
    entries = (
        WorkEntryInput(
            work_date=date(2026, 10, 14),
            category="paid_holiday",
            start_time=None,
            end_time=None,
            unpaid_break_minutes=0,
            paid_minutes=60,
        ),
    )

    with pytest.raises(IntegrityError) as raised:
        repository.save_payroll_run(record, entries, snapshot, payslip)

    assert not isinstance(raised.value, DuplicateMonthError)
    assert repository.count_rows("monthly_records") == 0


def test_snapshot_keeps_the_employment_dates(repository):
    repository.save_payroll_run(*make_run())

    with repository.engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT employment_start_date, employment_end_date "
                "FROM payroll_snapshots"
            )
        ).one()

    assert (row.employment_start_date, row.employment_end_date) == (
        "2026-01-01",
        "2026-12-15",
    )


def test_snapshot_without_an_end_date_stores_null(repository):
    record, entries, snapshot, payslip = make_run()
    open_ended = replace(
        snapshot, employment=replace(snapshot.employment, employment_end_date=None)
    )
    repository.save_payroll_run(record, entries, open_ended, payslip)

    with repository.engine.connect() as connection:
        end_date = connection.execute(
            text("SELECT employment_end_date FROM payroll_snapshots")
        ).scalar()

    assert end_date is None


def test_entries_keep_their_times_and_breaks(repository):
    repository.save_payroll_run(*make_run())

    with repository.engine.connect() as connection:
        row = connection.execute(
            text("SELECT start_time, end_time, unpaid_break_minutes, paid_minutes FROM work_entries")
        ).one()

    assert tuple(row) == ("09:00:00.000000", "13:00:00.000000", 15, 225)


def test_prior_run_carries_the_month(repository):
    repository.save_payroll_run(*make_run(month=9))

    assert repository.prior_run(employment_id=7).month == 9


def test_prior_run_is_none_before_the_first_run(repository):
    assert repository.prior_run(employment_id=7) is None


def test_prior_run_returns_the_latest_month(repository):
    repository.save_payroll_run(*make_run(month=9))
    repository.save_payroll_run(*make_run(month=10))

    prior = repository.prior_run(employment_id=7)

    assert prior is not None
    assert prior.monthly_record_id == 2


def test_gross_to_date_ignores_other_years(repository):
    repository.save_payroll_run(*make_run(year=2025, month=12))

    assert repository.employee_gross_to_date(employee_id=9, year=2026) == 0
    assert repository.employer_gross_to_date(employer_id=3, year=2026) == 0


def test_run_snapshot_round_trips_equal(repository):
    _, _, snapshot, _ = make_run()
    saved = repository.save_payroll_run(*make_run())

    assert repository.run_snapshot(saved.monthly_record_id) == snapshot


def test_run_snapshot_round_trips_without_an_end_date(repository):
    record, entries, snapshot, payslip = make_run()
    open_ended = replace(
        snapshot, employment=replace(snapshot.employment, employment_end_date=None)
    )
    saved = repository.save_payroll_run(record, entries, open_ended, payslip)

    assert repository.run_snapshot(saved.monthly_record_id) == open_ended


def test_run_snapshot_is_none_for_an_unknown_record(repository):
    assert repository.run_snapshot(99) is None


def test_run_snapshot_and_its_parts_are_frozen():
    _, _, snapshot, _ = make_run()

    for target, field in (
        (snapshot, "ruleset_version"),
        (snapshot.employment, "hourly_wage_cents"),
        (snapshot.hours, "worked"),
    ):
        with pytest.raises(FrozenInstanceError):
            setattr(target, field, getattr(target, field))


def test_changing_a_saved_snapshot_row_raises(repository):
    repository.save_payroll_run(*make_run())

    with Session(repository.engine) as session:
        row = session.get(PayrollSnapshotRow, 1)
        row.holiday_balance_minutes = 0
        with pytest.raises(ImmutableRecordError):
            session.flush()
        session.rollback()

    assert repository.prior_run(employment_id=7).holiday_balance_minutes == 1200


def test_deleting_a_saved_snapshot_row_raises(repository):
    repository.save_payroll_run(*make_run())

    with Session(repository.engine) as session:
        session.delete(session.get(PayrollSnapshotRow, 1))
        with pytest.raises(ImmutableRecordError):
            session.flush()
        session.rollback()

    assert repository.count_rows("payroll_snapshots") == 1


def test_changing_a_saved_work_entry_raises(repository):
    repository.save_payroll_run(*make_run())

    with Session(repository.engine) as session:
        row = session.get(WorkEntryRow, 1)
        row.paid_minutes = 0
        with pytest.raises(ImmutableRecordError):
            session.flush()
        session.rollback()

    with repository.engine.connect() as connection:
        paid = connection.execute(text("SELECT paid_minutes FROM work_entries")).scalar()
    assert paid == 225


def test_deleting_a_saved_work_entry_raises(repository):
    repository.save_payroll_run(*make_run())

    with Session(repository.engine) as session:
        session.delete(session.get(WorkEntryRow, 1))
        with pytest.raises(ImmutableRecordError):
            session.flush()
        session.rollback()

    assert repository.count_rows("work_entries") == 1


def test_a_run_for_an_unknown_employment_is_not_reported_as_a_duplicate_month(repository):
    record, entries, snapshot, payslip = make_run(employment_id=99)

    with pytest.raises(IntegrityError) as raised:
        repository.save_payroll_run(record, entries, snapshot, payslip)

    assert not isinstance(raised.value, DuplicateMonthError)
    for table in ("monthly_records", "work_entries", "payroll_snapshots", "payslips"):
        assert repository.count_rows(table) == 0


def test_a_snapshot_for_an_unknown_record_is_not_reported_as_a_duplicate(repository):
    _, _, snapshot, _ = make_run()

    with pytest.raises(IntegrityError) as raised:
        repository.save_snapshot(record_id=99, snapshot=snapshot)

    assert not isinstance(raised.value, DuplicateMonthError)


def test_employment_terms_reads_the_stored_integers(tmp_path):
    engine = create_database_engine(f"sqlite:///{tmp_path / 'payroll.db'}")
    create_schema(engine)
    add_employment(
        engine,
        employment_id=4,
        employer_id=2,
        employee_id=5,
        start_date=date(2026, 5, 1),
        hourly_wage_cents=2575,
        weekly_minutes=390,
        holiday_weeks=5,
    )

    stored = SqlAlchemyPayrollRepository(engine).employment_terms(4)

    assert stored == StoredEmployment(
        employer_id=2,
        employee_id=5,
        terms=EmploymentTerms(
            hourly_wage_cents=2575,
            weekly_minutes=390,
            holiday_weeks=5,
            employment_start_date=date(2026, 5, 1),
            employment_end_date=None,
        ),
    )
    with pytest.raises(FrozenInstanceError):
        stored.employer_id = 1
    engine.dispose()


def test_employment_terms_is_none_for_an_unknown_id(repository):
    assert repository.employment_terms(999) is None
