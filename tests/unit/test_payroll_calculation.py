# tests/unit/test_payroll_calculation.py

import unittest
from datetime import date, time
from decimal import Decimal

from src.app.domain.constants import (
    EMPLOYEE_GROSS_LIMIT,
    EMPLOYER_GROSS_LIMIT,
    PUBLIC_HOLIDAYS,
)
from src.app.domain.employment import Employment
from src.app.domain.errors import AnnualLimitExceededError, InvalidPayrollInputError
from src.app.domain.hour_categories import HourCategory, MinuteTotals
from src.app.domain.payroll_calculation import (
    AKBS_HOUSEHOLD_EMPLOYMENT_URL,
    ANNUAL_LIMIT_EXCEEDED_MESSAGE,
    calculate_employee_deductions,
    calculate_employer_costs,
    calculate_monthly_totals,
    calculate_paid_minutes,
    classify_public_holidays,
    generate_payslip,
    generate_payslip_from_terms,
    is_public_holiday,
    round_money,
    validate_annual_limits,
)
from src.app.domain.work_entry import WorkEntry, reject_overlapping_entries


class TestPayrollCalculation(unittest.TestCase):
    """Unit tests for the payroll calculation functions."""

    def setUp(self):
        """Set up test data."""
        self.employment = Employment(
            id=1,
            employer_id=1,
            employee_id=1,
            hourly_wage=25.0,
            weekly_hours=10
        )


    def test_paid_minutes_are_whole_minutes_after_unpaid_breaks(self):
        self.assertEqual(calculate_paid_minutes(time(9, 0), time(17, 30), 30), 480)
        self.assertEqual(calculate_paid_minutes(time(9, 0), time(13, 0), 0), 240)

    def test_paid_minutes_reject_breaks_longer_than_the_work(self):
        with self.assertRaises(InvalidPayrollInputError):
            calculate_paid_minutes(time(9, 0), time(10, 0), 61)

    def test_work_entry_carries_a_category_and_whole_minutes(self):
        entry = WorkEntry(
            work_date=date(2026, 5, 14),
            category=HourCategory.PUBLIC_HOLIDAY_WORKED,
            paid_minutes=240,
        )

        self.assertEqual(entry.category, HourCategory.PUBLIC_HOLIDAY_WORKED)
        self.assertEqual(entry.paid_minutes, 240)
        self.assertTrue(is_public_holiday(entry.work_date))

    def test_work_entry_rejects_negative_minutes(self):
        with self.assertRaises(InvalidPayrollInputError):
            WorkEntry(
                work_date=date(2026, 5, 14),
                category=HourCategory.WORKED,
                paid_minutes=-1,
            )

    def test_public_holiday_list_contains_nine_statutory_holidays(self):
        self.assertFalse(is_public_holiday(date(2026, 1, 2)))
        self.assertFalse(is_public_holiday(date(2026, 3, 2)))
        self.assertEqual(len(PUBLIC_HOLIDAYS), 9)

    def test_monthly_totals_sum_each_category(self):
        entries = [
            WorkEntry(date(2026, 5, 14), HourCategory.PUBLIC_HOLIDAY_WORKED, 240),
            WorkEntry(date(2026, 5, 15), HourCategory.WORKED, 240),
            WorkEntry(date(2026, 5, 16), HourCategory.ANNUAL_HOLIDAY_TAKEN, 60),
            WorkEntry(date(2026, 5, 17), HourCategory.PUBLIC_HOLIDAY_TAKEN, 30),
        ]

        self.assertEqual(
            calculate_monthly_totals(entries),
            MinuteTotals(
                worked=240,
                public_holiday_worked=240,
                annual_holiday_taken=60,
                public_holiday_taken=30,
            ),
        )

    def test_monthly_totals_reject_entries_from_another_month(self):
        entries = [
            WorkEntry(date(2026, 5, 14), HourCategory.WORKED, 240),
            WorkEntry(date(2026, 6, 1), HourCategory.WORKED, 240),
        ]

        with self.assertRaises(InvalidPayrollInputError):
            calculate_monthly_totals(entries)

    def test_monthly_totals_of_no_entries_are_all_zero(self):
        self.assertEqual(calculate_monthly_totals([]), MinuteTotals())

    def test_round_money_rounds_half_up_to_the_centime(self):
        self.assertEqual(round_money(Decimal("10.005")), Decimal("10.01"))
        self.assertEqual(round_money(Decimal("10.004")), Decimal("10.00"))
        self.assertEqual(round_money(Decimal("0.015")), Decimal("0.02"))

    def test_entry_from_times_derives_the_paid_minutes_and_keeps_the_times(self):
        entry = WorkEntry.from_times(
            date(2026, 10, 1), HourCategory.WORKED, time(9, 0), time(17, 30), 30
        )

        self.assertEqual(entry.paid_minutes, 480)
        self.assertEqual(entry.start_time, time(9, 0))
        self.assertEqual(entry.end_time, time(17, 30))
        self.assertEqual(entry.unpaid_break_minutes, 30)

    def test_entry_rejects_paid_minutes_that_contradict_its_times(self):
        with self.assertRaises(InvalidPayrollInputError):
            WorkEntry(
                date(2026, 10, 1), HourCategory.WORKED, 100,
                start_time=time(9, 0), end_time=time(17, 0),
            )

    def test_entry_rejects_a_start_time_without_an_end_time(self):
        with self.assertRaises(InvalidPayrollInputError):
            WorkEntry(date(2026, 10, 1), HourCategory.WORKED, 60, start_time=time(9, 0))

    def test_entry_rejects_an_end_before_the_start(self):
        with self.assertRaises(InvalidPayrollInputError):
            WorkEntry.from_times(
                date(2026, 10, 1), HourCategory.WORKED, time(17, 0), time(9, 0), 0
            )

    def test_overlapping_entries_on_one_day_are_rejected(self):
        entries = [
            WorkEntry.from_times(date(2026, 10, 1), HourCategory.WORKED, time(9), time(12), 0),
            WorkEntry.from_times(date(2026, 10, 1), HourCategory.WORKED, time(11), time(14), 0),
        ]

        with self.assertRaises(InvalidPayrollInputError):
            reject_overlapping_entries(entries)

    def test_an_entry_inside_another_is_an_overlap(self):
        entries = [
            WorkEntry.from_times(date(2026, 10, 1), HourCategory.WORKED, time(9), time(17), 0),
            WorkEntry.from_times(date(2026, 10, 1), HourCategory.WORKED, time(10), time(11), 0),
        ]

        with self.assertRaises(InvalidPayrollInputError):
            reject_overlapping_entries(entries)

    def test_several_non_overlapping_entries_on_one_day_are_valid(self):
        entries = [
            WorkEntry.from_times(date(2026, 10, 1), HourCategory.WORKED, time(14), time(17), 0),
            WorkEntry.from_times(date(2026, 10, 1), HourCategory.WORKED, time(9), time(12), 0),
            WorkEntry.from_times(date(2026, 10, 1), HourCategory.WORKED, time(12), time(14), 0),
        ]

        reject_overlapping_entries(entries)

    def test_the_same_hours_on_different_days_do_not_overlap(self):
        entries = [
            WorkEntry.from_times(date(2026, 10, 1), HourCategory.WORKED, time(9), time(12), 0),
            WorkEntry.from_times(date(2026, 10, 2), HourCategory.WORKED, time(9), time(12), 0),
        ]

        reject_overlapping_entries(entries)

    def test_work_on_a_public_holiday_is_classified_as_public_holiday_worked(self):
        entries = [
            WorkEntry(date(2026, 5, 14), HourCategory.WORKED, 240),
            WorkEntry(date(2026, 5, 15), HourCategory.WORKED, 240),
        ]

        classified = classify_public_holidays(entries)

        self.assertEqual(classified[0].category, HourCategory.PUBLIC_HOLIDAY_WORKED)
        self.assertEqual(classified[1].category, HourCategory.WORKED)

    def test_classification_keeps_times_and_minutes(self):
        entry = WorkEntry.from_times(
            date(2026, 5, 14), HourCategory.WORKED, time(9), time(13), 15
        )

        classified = classify_public_holidays([entry])[0]

        self.assertEqual(classified.paid_minutes, 225)
        self.assertEqual(classified.start_time, time(9))
        self.assertEqual(classified.unpaid_break_minutes, 15)

    def test_public_holiday_worked_on_an_ordinary_day_is_rejected(self):
        entries = [WorkEntry(date(2026, 5, 15), HourCategory.PUBLIC_HOLIDAY_WORKED, 240)]

        with self.assertRaises(InvalidPayrollInputError):
            classify_public_holidays(entries)

    def test_public_holiday_leave_on_an_ordinary_day_is_rejected(self):
        entries = [WorkEntry(date(2026, 5, 15), HourCategory.PUBLIC_HOLIDAY_TAKEN, 240)]

        with self.assertRaises(InvalidPayrollInputError):
            classify_public_holidays(entries)

    def test_public_holiday_leave_and_public_holiday_work_are_kept_on_a_holiday(self):
        entries = [
            WorkEntry(date(2026, 5, 14), HourCategory.PUBLIC_HOLIDAY_TAKEN, 240),
            WorkEntry(date(2026, 8, 1), HourCategory.PUBLIC_HOLIDAY_WORKED, 240),
        ]

        self.assertEqual(classify_public_holidays(entries), entries)

    def test_paid_holiday_on_a_public_holiday_is_rejected(self):
        entries = [WorkEntry(date(2026, 5, 14), HourCategory.ANNUAL_HOLIDAY_TAKEN, 240)]

        with self.assertRaises(InvalidPayrollInputError):
            classify_public_holidays(entries)

    def test_paid_holiday_on_an_ordinary_day_is_kept(self):
        entries = [WorkEntry(date(2026, 5, 15), HourCategory.ANNUAL_HOLIDAY_TAKEN, 240)]

        self.assertEqual(classify_public_holidays(entries), entries)

    def test_public_holiday_leave_with_public_holiday_work_on_one_day_is_rejected(self):
        entries = [
            WorkEntry(date(2026, 5, 14), HourCategory.PUBLIC_HOLIDAY_TAKEN, 240),
            WorkEntry(date(2026, 5, 14), HourCategory.PUBLIC_HOLIDAY_WORKED, 60),
        ]

        with self.assertRaises(InvalidPayrollInputError):
            classify_public_holidays(entries)

    def test_public_holiday_leave_with_work_on_a_holiday_is_rejected_after_classification(self):
        entries = [
            WorkEntry(date(2026, 5, 14), HourCategory.PUBLIC_HOLIDAY_TAKEN, 240),
            WorkEntry(date(2026, 5, 14), HourCategory.WORKED, 60),
        ]

        with self.assertRaises(InvalidPayrollInputError):
            classify_public_holidays(entries)

    def test_paid_holiday_with_public_holiday_leave_on_one_day_is_rejected(self):
        entries = [
            WorkEntry(date(2026, 5, 14), HourCategory.ANNUAL_HOLIDAY_TAKEN, 60),
            WorkEntry(date(2026, 5, 14), HourCategory.PUBLIC_HOLIDAY_TAKEN, 60),
        ]

        with self.assertRaises(InvalidPayrollInputError):
            classify_public_holidays(entries)

    def test_several_public_holiday_work_entries_on_one_day_are_valid(self):
        entries = [
            WorkEntry.from_times(date(2026, 5, 14), HourCategory.WORKED, time(9), time(12)),
            WorkEntry.from_times(date(2026, 5, 14), HourCategory.WORKED, time(14), time(17)),
        ]

        classified = classify_public_holidays(entries)

        self.assertEqual(
            [entry.category for entry in classified],
            [HourCategory.PUBLIC_HOLIDAY_WORKED] * 2,
        )

    def test_calculate_employee_deductions(self):
        ahv, alv, tax, nbu = calculate_employee_deductions(
            gross_wage=Decimal("4000.00"), weekly_minutes=600
        )
        self.assertEqual(ahv, Decimal("212.00"))
        self.assertEqual(alv, Decimal("44.00"))
        self.assertEqual(tax, Decimal("200.00"))
        self.assertEqual(nbu, Decimal("57.28"))

        ahv, alv, tax, nbu = calculate_employee_deductions(
            gross_wage=Decimal("4000.00"), weekly_minutes=300
        )
        self.assertEqual(nbu, Decimal("0.00"))

    def test_admin_charge_uses_total_ahv_on_500_85(self):
        self.assertEqual(
            calculate_employer_costs(Decimal("500.85"))[-1], Decimal("2.65")
        )

    def test_admin_charge_keeps_cents_for_880(self):
        """AKBS prints 4.70 after rounding its lines to 5 Rappen; we keep cents."""
        self.assertEqual(
            calculate_employer_costs(Decimal("880.00"))[-1], Decimal("4.66")
        )

    def test_calculate_employer_costs(self):
        employer_ahv, employer_alv, employer_fak, employer_bu, admin_charge = (
            calculate_employer_costs(gross_wage=Decimal("4000.00"))
        )
        self.assertEqual(employer_ahv, Decimal("212.00"))
        self.assertEqual(employer_alv, Decimal("44.00"))
        self.assertEqual(employer_fak, Decimal("66.00"))
        self.assertEqual(employer_bu, Decimal("20.20"))
        self.assertEqual(admin_charge, Decimal("21.20"))

    def test_generate_payslip_from_terms_matches_the_employment_version(self):
        totals = MinuteTotals(worked=9600, annual_holiday_taken=480)

        from_terms = generate_payslip_from_terms(
            totals=totals,
            hourly_wage=Decimal(str(self.employment.hourly_wage)),
            weekly_minutes=round(self.employment.weekly_hours * 60),
            cash_bonus=Decimal("100.00"),
            expense_reimbursements=Decimal("50.00"),
        )
        from_employment = generate_payslip(
            totals=totals,
            employment=self.employment,
            cash_bonus=Decimal("100.00"),
            expense_reimbursements=Decimal("50.00"),
        )

        self.assertEqual(from_terms, from_employment)

    def test_generate_payslip(self):
        totals = MinuteTotals(
            worked=9600,
            public_holiday_worked=240,
            annual_holiday_taken=480,
        )

        payslip = generate_payslip(
            totals=totals,
            employment=self.employment,
            cash_bonus=Decimal("100.00"),
            expense_reimbursements=Decimal("50.00"),
        )

        self.assertEqual(payslip.gross_wage, Decimal("4450.00"))
        self.assertEqual(payslip.ahv_deduction, Decimal("235.85"))
        self.assertEqual(payslip.alv_deduction, Decimal("48.95"))
        self.assertEqual(payslip.tax_deduction, Decimal("222.50"))
        self.assertEqual(payslip.nbu_deduction, Decimal("63.72"))
        self.assertEqual(payslip.net_payout, Decimal("3928.98"))
        self.assertEqual(payslip.employer_ahv, Decimal("235.85"))
        self.assertEqual(payslip.employer_alv, Decimal("48.95"))
        self.assertEqual(payslip.employer_fak, Decimal("73.43"))
        self.assertEqual(payslip.employer_bu, Decimal("22.47"))
        self.assertEqual(payslip.admin_charge, Decimal("23.59"))
        self.assertEqual(payslip.total_employer_cost, Decimal("4904.29"))

    def test_validate_annual_limits(self):
        validate_annual_limits(
            current_gross_wage=Decimal("4000.00"),
            employee_gross_to_date=Decimal("18000.00"),
            employer_gross_to_date=Decimal("50000.00"),
        )

        with self.assertRaises(AnnualLimitExceededError):
            validate_annual_limits(
                current_gross_wage=Decimal("5000.00"),
                employee_gross_to_date=Decimal("18000.00"),
                employer_gross_to_date=Decimal("0.00"),
            )

        with self.assertRaises(AnnualLimitExceededError):
            validate_annual_limits(
                current_gross_wage=Decimal("5000.00"),
                employee_gross_to_date=Decimal("0.00"),
                employer_gross_to_date=Decimal("56000.00"),
            )

    def test_employee_annual_limit_message_explains_next_step(self):
        with self.assertRaises(AnnualLimitExceededError) as error:
            validate_annual_limits(
                current_gross_wage=Decimal("1.00"),
                employee_gross_to_date=Decimal(EMPLOYEE_GROSS_LIMIT),
            )

        message = str(error.exception)
        self.assertEqual(
            message,
            ANNUAL_LIMIT_EXCEEDED_MESSAGE.format(
                limit_owner="Employee", limit_amount=EMPLOYEE_GROSS_LIMIT
            ),
        )
        self.assertIn("The simplified procedure no longer applies.", message)
        self.assertIn("Contact AKBS about the ordinary procedure", message)
        self.assertIn("PayAlign does not support", message)
        self.assertTrue(AKBS_HOUSEHOLD_EMPLOYMENT_URL.startswith("https://ak-bs.ch/"))
        self.assertIn(AKBS_HOUSEHOLD_EMPLOYMENT_URL, message)

    def test_employer_annual_limit_message_explains_next_step(self):
        with self.assertRaises(AnnualLimitExceededError) as error:
            validate_annual_limits(
                current_gross_wage=Decimal("1.00"),
                employer_gross_to_date=Decimal(EMPLOYER_GROSS_LIMIT),
            )

        self.assertEqual(
            str(error.exception),
            ANNUAL_LIMIT_EXCEEDED_MESSAGE.format(
                limit_owner="Employer", limit_amount=EMPLOYER_GROSS_LIMIT
            ),
        )


if __name__ == "__main__":
    unittest.main()
