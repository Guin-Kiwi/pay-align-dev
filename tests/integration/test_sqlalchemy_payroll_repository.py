from datetime import date, time

import pytest
from src.app.domain.errors import (
    DuplicateMonthError,
    InvalidHolidayBalanceError,
)
from src.app.infrastructure.database import create_database_engine, create_schema
from src.app.infrastructure.sqlalchemy_payroll_repository import (
    MonthlyRecordInput,
    PayrollSnapshotInput,
    PayslipInput,
    SqlAlchemyPayrollRepository,
    WorkEntryInput,
)


@pytest.fixture
def repository(tmp_path):
    engine = create_database_engine(f"sqlite:///{tmp_path / 'payroll.db'}")
    create_schema(engine)
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
    snapshot = PayrollSnapshotInput(
        hourly_wage_cents=2500,
        weekly_minutes=600,
        holiday_weeks=4,
        ruleset_version="2026",
        worked_minutes=225,
        public_holiday_worked_minutes=0,
        annual_holiday_taken_minutes=0,
        public_holiday_taken_minutes=0,
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
    invalid_snapshot = snapshot.__class__(
        **{**snapshot.__dict__, "holiday_balance_minutes": -1}
    )

    with pytest.raises(InvalidHolidayBalanceError):
        repository.save_payroll_run(record, entries, invalid_snapshot, payslip)

    for table in ("monthly_records", "work_entries", "payroll_snapshots", "payslips"):
        assert repository.count_rows(table) == 0
