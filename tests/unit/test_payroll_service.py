# tests/unit/test_payroll_service.py

import unittest
import pytest
from datetime import date, time
from decimal import Decimal

from src.app.application.payroll_service import PayrollService
from src.app.application.ports.payroll_repository import (
    EmploymentTerms,
    StoredEmployment,
    PayrollRepositoryPort,
    PriorRun,
    RunSnapshot,
    SavedPayrollRun,
)
from src.app.domain.errors import (
    AnnualLimitExceededError,
    DuplicateMonthError,
    EmploymentNotFoundError,
    InvalidHolidayBalanceError,
    InvalidPayrollInputError,
)
from src.app.domain.holiday_balance import holiday_entitlement_minutes
from src.app.domain.hour_categories import HourCategory, MinuteTotals
from src.app.domain.work_entry import WorkEntry


def make_employment(**overrides):
    terms = dict(
        hourly_wage_cents=2500,
        weekly_minutes=600,
        holiday_weeks=4,
        employment_start_date=date(2026, 10, 1),
        employment_end_date=None,
    )
    for key in ("start_date", "end_date"):
        if key in overrides:
            terms[f"employment_{key}"] = overrides.pop(key)
    return StoredEmployment(
        employer_id=3,
        employee_id=9,
        terms=EmploymentTerms(**{**terms, **overrides}),
    )


class FakePayrollRepository(PayrollRepositoryPort):
    """In-memory stand-in for PayrollRepositoryPort."""

    def __init__(self, prior=None, employee_to_date=0, employer_to_date=0):
        self.employment = make_employment()
        self.prior = prior
        self.employee_to_date = employee_to_date
        self.employer_to_date = employer_to_date
        self.saved = None
        self.duplicate = False
        self.gross_requests = []

    def save_payroll_run(self, record, entries, snapshot, payslip):
        if self.duplicate:
            raise DuplicateMonthError("Payroll month already exists.")
        self.saved = (record, entries, snapshot, payslip)
        return SavedPayrollRun(monthly_record_id=1, payslip_id=1)

    def run_snapshot(self, monthly_record_id):
        return None

    def employee_gross_to_date(self, employee_id, employer_id, year):
        self.gross_requests.append(("employee", employee_id, employer_id, year))
        return self.employee_to_date

    def employer_gross_to_date(self, employer_id, year):
        self.gross_requests.append(("employer", employer_id, year))
        return self.employer_to_date

    def prior_run(self, employment_id):
        return self.prior

    def employment_terms(self, employment_id, account_id):
        return self.employment if employment_id == 7 and account_id == 3 else None


def test_payroll_cannot_be_called_without_an_account():
    repository = FakePayrollRepository()
    with pytest.raises(TypeError):
        PayrollService().process_monthly_payroll(
            repository=repository, employment_id=7, month=10, year=2026, work_entries=[]
        )
    assert repository.saved is None


@pytest.mark.parametrize("account_id", [None, False, 0, -1])
def test_payroll_rejects_invalid_account_context_before_accessing_records(account_id):
    repository = FakePayrollRepository()
    with pytest.raises(InvalidPayrollInputError, match="authenticated account"):
        PayrollService().process_monthly_payroll(
            repository=repository, employment_id=7, month=10, year=2026,
            work_entries=[], account_id=account_id,
        )
    assert repository.saved is None
    assert repository.gross_requests == []


class TestPayrollService(unittest.TestCase):
    """Unit tests for PayrollService."""

    def setUp(self):
        self.service = PayrollService()

    def test_processes_a_month_and_saves_one_run(self):
        repository = FakePayrollRepository()

        record, payslip = self.service.process_monthly_payroll(
            repository=repository,
            account_id=3,
            employment_id=7,
            month=10,
            year=2026,
            work_entries=[
                WorkEntry(date(2026, 10, 1), HourCategory.WORKED, 600),
            ],
        )

        self.assertEqual(record.employment_id, 7)
        self.assertEqual(record.employee_id, 9)
        self.assertEqual(record.employer_id, 3)
        self.assertEqual(record.month, 10)
        self.assertEqual(record.year, 2026)
        self.assertEqual(payslip.gross_wage, Decimal("250.00"))
        self.assertEqual(repository.saved[0].employment_id, 7)
        self.assertEqual(repository.saved[0].employee_id, 9)
        self.assertEqual(repository.saved[0].employer_id, 3)
        self.assertEqual(repository.saved[0].month, 10)
        self.assertEqual(repository.saved[0].year, 2026)

    def test_an_unknown_employment_is_rejected_and_nothing_is_saved(self):
        repository = FakePayrollRepository()

        with self.assertRaises(EmploymentNotFoundError):
            self.service.process_monthly_payroll(
                repository=repository,
                account_id=3,
                employment_id=999,
                month=10,
                year=2026,
                work_entries=[],
            )

        self.assertIsNone(repository.saved)

    def test_employer_and_employee_come_from_the_stored_employment(self):
        repository = FakePayrollRepository()
        repository.employment = make_employment()

        record, _ = self.run_month(repository, month=10)

        self.assertEqual((record.employer_id, record.employee_id), (3, 9))
        self.assertEqual(
            (repository.saved[0].employer_id, repository.saved[0].employee_id), (3, 9)
        )

    def test_the_wage_is_the_stored_cents_divided_by_100(self):
        repository = FakePayrollRepository()
        repository.employment = make_employment(hourly_wage_cents=2575)

        _, payslip = self.run_month(
            repository,
            month=10,
            entries=[WorkEntry(date(2026, 10, 1), HourCategory.WORKED, 600)],
        )

        self.assertEqual(payslip.gross_wage, Decimal("257.50"))
        self.assertEqual(repository.saved[2].employment.hourly_wage_cents, 2575)

    def test_gross_to_date_is_read_for_the_whole_year_of_this_employer(self):
        repository = FakePayrollRepository()

        self.service.process_monthly_payroll(
            repository=repository,
            account_id=3,
            employment_id=7,
            month=10,
            year=2026,
            work_entries=[WorkEntry(date(2026, 10, 1), HourCategory.WORKED, 600)],
        )

        self.assertEqual(
            repository.gross_requests,
            [("employee", 9, 3, 2026), ("employer", 3, 2026)],
        )

    def test_snapshot_freezes_employment_values_and_minute_totals(self):
        repository = FakePayrollRepository()

        self.service.process_monthly_payroll(
            repository=repository,
            account_id=3,
            employment_id=7,
            month=10,
            year=2026,
            work_entries=[
                WorkEntry(date(2026, 10, 1), HourCategory.WORKED, 600),
                WorkEntry(date(2026, 10, 2), HourCategory.ANNUAL_HOLIDAY_TAKEN, 120),
            ],
        )

        snapshot = repository.saved[2]
        self.assertIsInstance(snapshot, RunSnapshot)
        self.assertEqual(
            snapshot.employment,
            EmploymentTerms(
                hourly_wage_cents=2500,
                weekly_minutes=600,
                holiday_weeks=4,
                employment_start_date=date(2026, 10, 1),
                employment_end_date=None,
            ),
        )
        self.assertEqual(snapshot.ruleset_version, "2026")
        self.assertEqual(
            snapshot.hours,
            MinuteTotals(worked=600, annual_holiday_taken=120),
        )

    def test_first_run_starts_from_the_prorated_entitlement(self):
        repository = FakePayrollRepository()

        self.service.process_monthly_payroll(
            repository=repository,
            account_id=3,
            employment_id=7,
            month=10,
            year=2026,
            work_entries=[
                WorkEntry(date(2026, 10, 2), HourCategory.ANNUAL_HOLIDAY_TAKEN, 120),
            ],
        )

        entitlement = holiday_entitlement_minutes(4, 600, date(2026, 10, 1))
        self.assertEqual(entitlement, 605)
        self.assertEqual(repository.saved[2].holiday_balance_minutes, entitlement - 120)

    def test_later_run_continues_from_the_prior_balance(self):
        repository = FakePayrollRepository(prior=PriorRun(1, 2026, 9, 1000))

        self.service.process_monthly_payroll(
            repository=repository,
            account_id=3,
            employment_id=7,
            month=10,
            year=2026,
            work_entries=[
                WorkEntry(date(2026, 10, 2), HourCategory.ANNUAL_HOLIDAY_TAKEN, 120),
            ],
        )

        self.assertEqual(repository.saved[2].holiday_balance_minutes, 880)

    def test_rejects_a_run_that_exceeds_the_employee_limit(self):
        repository = FakePayrollRepository(employee_to_date=22_500_00)

        with self.assertRaises(AnnualLimitExceededError):
            self.service.process_monthly_payroll(
                repository=repository,
                account_id=3,
                employment_id=7,
                month=10,
                year=2026,
                work_entries=[
                    WorkEntry(date(2026, 10, 1), HourCategory.WORKED, 600),
                ],
            )

        self.assertIsNone(repository.saved)

    def test_rejects_a_run_that_exceeds_the_employer_limit(self):
        repository = FakePayrollRepository(employer_to_date=60_400_00)

        with self.assertRaises(AnnualLimitExceededError):
            self.service.process_monthly_payroll(
                repository=repository,
                account_id=3,
                employment_id=7,
                month=10,
                year=2026,
                work_entries=[
                    WorkEntry(date(2026, 10, 1), HourCategory.WORKED, 600),
                ],
            )

        self.assertIsNone(repository.saved)

    def test_rejects_holiday_taken_beyond_the_balance(self):
        repository = FakePayrollRepository(prior=PriorRun(1, 2026, 9, 60))

        with self.assertRaises(InvalidHolidayBalanceError):
            self.service.process_monthly_payroll(
                repository=repository,
                account_id=3,
                employment_id=7,
                month=10,
                year=2026,
                work_entries=[
                    WorkEntry(date(2026, 10, 2), HourCategory.ANNUAL_HOLIDAY_TAKEN, 120),
                ],
            )

        self.assertIsNone(repository.saved)

    def test_a_month_without_entries_is_still_a_run_with_an_empty_payslip(self):
        repository = FakePayrollRepository()

        record, payslip = self.service.process_monthly_payroll(
            repository=repository,
            account_id=3,
            employment_id=7,
            month=10,
            year=2026,
            work_entries=[],
        )

        saved_record, entries, snapshot, saved_payslip = repository.saved
        self.assertEqual(entries, ())
        self.assertEqual(payslip.gross_wage, Decimal("0.00"))
        self.assertEqual(saved_payslip.gross_wage_cents, 0)
        self.assertEqual(snapshot.hours.worked, 0)
        self.assertEqual(snapshot.holiday_balance_minutes, 605)
        self.assertEqual(record.month, 10)

    def test_an_empty_month_keeps_the_prior_holiday_balance(self):
        repository = FakePayrollRepository(prior=PriorRun(1, 2026, 9, 1000))

        self.service.process_monthly_payroll(
            repository=repository,
            account_id=3,
            employment_id=7,
            month=10,
            year=2026,
            work_entries=[],
        )

        self.assertEqual(repository.saved[2].holiday_balance_minutes, 1000)

    def test_rejects_entries_from_another_month(self):
        repository = FakePayrollRepository()

        with self.assertRaises(InvalidPayrollInputError):
            self.service.process_monthly_payroll(
                repository=repository,
                account_id=3,
                employment_id=7,
                month=10,
                year=2026,
                work_entries=[
                    WorkEntry(date(2026, 9, 30), HourCategory.WORKED, 600),
                ],
            )

        self.assertIsNone(repository.saved)

    def test_duplicate_month_propagates_and_saves_nothing(self):
        repository = FakePayrollRepository()
        repository.duplicate = True

        with self.assertRaises(DuplicateMonthError):
            self.service.process_monthly_payroll(
                repository=repository,
                account_id=3,
                employment_id=7,
                month=10,
                year=2026,
                work_entries=[
                    WorkEntry(date(2026, 10, 1), HourCategory.WORKED, 600),
                ],
            )

        self.assertIsNone(repository.saved)


    def run_month(self, repository, month, year=2026, entries=None, **overrides):
        if "employment" in overrides:
            repository.employment = overrides.pop("employment")
        return self.service.process_monthly_payroll(
            repository=repository,
            account_id=3,
            employment_id=7,
            month=month,
            year=year,
            work_entries=entries or [],
            **overrides,
        )

    def test_first_run_must_be_the_month_of_the_start_date(self):
        repository = FakePayrollRepository()

        with self.assertRaises(InvalidPayrollInputError):
            self.run_month(repository, month=11)
        with self.assertRaises(InvalidPayrollInputError):
            self.run_month(repository, month=9)

        self.assertIsNone(repository.saved)

    def test_a_later_run_is_the_month_after_the_last_saved_run(self):
        repository = FakePayrollRepository(prior=PriorRun(1, 2026, 10, 500))

        self.run_month(repository, month=11)

        self.assertEqual(repository.saved[0].month, 11)

    def test_a_skipped_month_is_rejected(self):
        repository = FakePayrollRepository(prior=PriorRun(1, 2026, 10, 500))

        with self.assertRaises(InvalidPayrollInputError):
            self.run_month(repository, month=12)

        self.assertIsNone(repository.saved)

    def test_a_month_that_is_not_after_the_last_run_is_a_duplicate(self):
        repository = FakePayrollRepository(prior=PriorRun(1, 2026, 11, 500))

        with self.assertRaises(DuplicateMonthError):
            self.run_month(repository, month=11)
        with self.assertRaises(DuplicateMonthError):
            self.run_month(repository, month=10)

        self.assertIsNone(repository.saved)

    def test_bonus_and_expenses_are_rounded_half_up_once_on_entry(self):
        repository = FakePayrollRepository()

        record, payslip = self.run_month(
            repository,
            month=10,
            cash_bonus=Decimal("10.005"),
            expense_reimbursements=Decimal("5.555"),
        )

        saved_record = repository.saved[0]
        self.assertEqual(record.cash_bonus, Decimal("10.01"))
        self.assertEqual(record.expense_reimbursements, Decimal("5.56"))
        self.assertEqual(saved_record.cash_bonus_cents, 1001)
        self.assertEqual(saved_record.expense_reimbursements_cents, 556)
        self.assertEqual(payslip.gross_wage, Decimal("10.01"))

    def test_a_sub_centime_amount_is_not_truncated_to_zero(self):
        repository = FakePayrollRepository()

        self.run_month(
            repository, month=10, expense_reimbursements=Decimal("0.005")
        )

        self.assertEqual(repository.saved[0].expense_reimbursements_cents, 1)

    def test_entries_are_saved_as_submitted(self):
        repository = FakePayrollRepository()

        self.run_month(
            repository,
            month=10,
            entries=[
                WorkEntry.from_times(
                    date(2026, 10, 1), HourCategory.WORKED, time(9), time(13), 15
                ),
                WorkEntry(date(2026, 10, 2), HourCategory.ANNUAL_HOLIDAY_TAKEN, 120),
            ],
        )

        timed, minutes_only = repository.saved[1]
        self.assertEqual(
            (timed.start_time, timed.end_time, timed.unpaid_break_minutes, timed.paid_minutes),
            (time(9), time(13), 15, 225),
        )
        self.assertEqual(
            (minutes_only.start_time, minutes_only.end_time, minutes_only.paid_minutes),
            (None, None, 120),
        )

    def test_several_entries_on_one_day_are_all_saved(self):
        repository = FakePayrollRepository()

        self.run_month(
            repository,
            month=10,
            entries=[
                WorkEntry.from_times(date(2026, 10, 1), HourCategory.WORKED, time(9), time(12)),
                WorkEntry.from_times(date(2026, 10, 1), HourCategory.WORKED, time(14), time(17)),
            ],
        )

        self.assertEqual(len(repository.saved[1]), 2)
        self.assertEqual(repository.saved[2].hours.worked, 360)

    def test_overlapping_entries_are_rejected_and_nothing_is_saved(self):
        repository = FakePayrollRepository()

        with self.assertRaises(InvalidPayrollInputError):
            self.run_month(
                repository,
                month=10,
                entries=[
                    WorkEntry.from_times(date(2026, 10, 1), HourCategory.WORKED, time(9), time(12)),
                    WorkEntry.from_times(date(2026, 10, 1), HourCategory.WORKED, time(11), time(13)),
                ],
            )

        self.assertIsNone(repository.saved)

    def test_work_on_a_public_holiday_is_saved_and_paid_as_public_holiday_work(self):
        repository = FakePayrollRepository()
        employment = make_employment(start_date=date(2026, 5, 1))

        _, payslip = self.run_month(
            repository,
            month=5,
            employment=employment,
            entries=[
                WorkEntry.from_times(date(2026, 5, 14), HourCategory.WORKED, time(9), time(13)),
            ],
        )

        saved_entry = repository.saved[1][0]
        self.assertEqual(saved_entry.category, "public_holiday_worked")
        self.assertEqual(repository.saved[2].hours.public_holiday_worked, 240)
        self.assertEqual(repository.saved[2].hours.worked, 0)
        self.assertEqual(payslip.gross_wage, Decimal("150.00"))

    def test_public_holiday_leave_on_an_ordinary_day_is_rejected(self):
        repository = FakePayrollRepository()

        with self.assertRaises(InvalidPayrollInputError):
            self.run_month(
                repository,
                month=10,
                entries=[WorkEntry(date(2026, 10, 1), HourCategory.PUBLIC_HOLIDAY_TAKEN, 60)],
            )

        self.assertIsNone(repository.saved)

    def test_paid_holiday_on_a_public_holiday_is_rejected_and_nothing_is_saved(self):
        repository = FakePayrollRepository()

        with self.assertRaises(InvalidPayrollInputError):
            self.run_month(
                repository,
                month=5,
                employment=make_employment(start_date=date(2026, 5, 1)),
                entries=[WorkEntry(date(2026, 5, 14), HourCategory.ANNUAL_HOLIDAY_TAKEN, 60)],
            )

        self.assertIsNone(repository.saved)

    def test_public_holiday_leave_with_work_on_the_same_day_is_rejected(self):
        repository = FakePayrollRepository()

        with self.assertRaises(InvalidPayrollInputError):
            self.run_month(
                repository,
                month=5,
                employment=make_employment(start_date=date(2026, 5, 1)),
                entries=[
                    WorkEntry(date(2026, 5, 14), HourCategory.PUBLIC_HOLIDAY_TAKEN, 60),
                    WorkEntry.from_times(
                        date(2026, 5, 14), HourCategory.WORKED, time(9), time(10)
                    ),
                ],
            )

        self.assertIsNone(repository.saved)

    def test_a_run_after_the_end_month_is_rejected_and_nothing_is_saved(self):
        repository = FakePayrollRepository(prior=PriorRun(1, 2026, 10, 500))
        employment = make_employment(end_date=date(2026, 10, 15))

        with self.assertRaises(InvalidPayrollInputError):
            self.run_month(repository, month=11, employment=employment)

        self.assertIsNone(repository.saved)

    def test_a_run_long_after_the_end_month_is_rejected_as_ended(self):
        repository = FakePayrollRepository(prior=PriorRun(1, 2026, 10, 500))
        employment = make_employment(end_date=date(2026, 10, 15))

        with self.assertRaisesRegex(InvalidPayrollInputError, "ended"):
            self.run_month(repository, month=12, employment=employment)

        self.assertIsNone(repository.saved)

    def test_the_end_month_itself_is_still_processed(self):
        repository = FakePayrollRepository()
        employment = make_employment(end_date=date(2026, 10, 15))

        self.run_month(repository, month=10, employment=employment)

        self.assertEqual(repository.saved[0].month, 10)

    def test_a_duplicate_of_the_end_month_is_still_a_duplicate(self):
        repository = FakePayrollRepository(prior=PriorRun(1, 2026, 10, 500))
        employment = make_employment(end_date=date(2026, 10, 15))

        with self.assertRaises(DuplicateMonthError):
            self.run_month(repository, month=10, employment=employment)

    def test_entries_on_the_start_and_end_dates_are_accepted(self):
        repository = FakePayrollRepository()
        employment = make_employment(
            start_date=date(2026, 10, 5), end_date=date(2026, 10, 20)
        )

        self.run_month(
            repository,
            month=10,
            employment=employment,
            entries=[
                WorkEntry(date(2026, 10, 5), HourCategory.WORKED, 60),
                WorkEntry(date(2026, 10, 20), HourCategory.WORKED, 60),
            ],
        )

        self.assertEqual(len(repository.saved[1]), 2)

    def test_an_entry_before_the_start_date_is_rejected_and_nothing_is_saved(self):
        repository = FakePayrollRepository()
        employment = make_employment(start_date=date(2026, 10, 5))

        with self.assertRaises(InvalidPayrollInputError):
            self.run_month(
                repository,
                month=10,
                employment=employment,
                entries=[WorkEntry(date(2026, 10, 4), HourCategory.WORKED, 60)],
            )

        self.assertIsNone(repository.saved)

    def test_an_entry_after_the_end_date_is_rejected_and_nothing_is_saved(self):
        repository = FakePayrollRepository()
        employment = make_employment(end_date=date(2026, 10, 20))

        with self.assertRaises(InvalidPayrollInputError):
            self.run_month(
                repository,
                month=10,
                employment=employment,
                entries=[WorkEntry(date(2026, 10, 21), HourCategory.WORKED, 60)],
            )

        self.assertIsNone(repository.saved)

    def test_a_leave_entry_outside_the_employment_is_rejected_too(self):
        repository = FakePayrollRepository()
        employment = make_employment(end_date=date(2026, 10, 20))

        with self.assertRaises(InvalidPayrollInputError):
            self.run_month(
                repository,
                month=10,
                employment=employment,
                entries=[
                    WorkEntry(date(2026, 10, 21), HourCategory.ANNUAL_HOLIDAY_TAKEN, 60)
                ],
            )

        self.assertIsNone(repository.saved)

    def test_snapshot_keeps_the_employment_dates(self):
        repository = FakePayrollRepository()
        employment = make_employment(end_date=date(2026, 12, 15))

        self.run_month(repository, month=10, employment=employment)

        snapshot = repository.saved[2]
        self.assertEqual(snapshot.employment.employment_start_date, date(2026, 10, 1))
        self.assertEqual(snapshot.employment.employment_end_date, date(2026, 12, 15))

    def test_snapshot_end_date_is_none_without_an_end_date(self):
        repository = FakePayrollRepository()

        self.run_month(repository, month=10)

        self.assertIsNone(repository.saved[2].employment.employment_end_date)


if __name__ == "__main__":
    unittest.main()
