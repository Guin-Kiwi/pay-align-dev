# tests/unit/test_payroll_calculation.py

import unittest
from datetime import date, time

from src.app.domain.constants import PUBLIC_HOLIDAYS_2026
from src.app.domain.employment import Employment
from src.app.domain.errors import AnnualLimitExceededError, InvalidPayrollInputError
from src.app.domain.monthly_record import MonthlyRecord
from src.app.domain.payroll_calculation import (
    calculate_employee_deductions,
    calculate_employer_costs,
    calculate_gross_wage,
    calculate_monthly_hours,
    calculate_paid_hours,
    generate_payslip,
    is_public_holiday,
    validate_annual_limits,
)
from src.app.domain.work_entry import WorkEntry


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


    def test_calculate_gross_wage(self):
        """Test gross wage calculation."""
        # Standard case
        gross_wage = calculate_gross_wage(
            hours_worked=160,
            hourly_wage=25.0,
            holiday_hours=8,
            public_holiday_hours=4,
            cash_bonus=100
        )
        self.assertEqual(gross_wage, 4450.0)  # (160 + 8 + 4) * 25 + (4 * 25 * 0.5) + 100

        # No public holiday hours
        gross_wage = calculate_gross_wage(
            hours_worked=160,
            hourly_wage=25.0,
            holiday_hours=8
        )
        self.assertEqual(gross_wage, 4200.0)  # (160 + 8) * 25

        # No holiday hours or bonus
        gross_wage = calculate_gross_wage(
            hours_worked=160,
            hourly_wage=25.0
        )
        self.assertEqual(gross_wage, 4000.0)  # 160 * 25

    def test_work_entry_calculates_paid_hours_and_public_holiday(self):
        entry = WorkEntry(
            work_date=date(2026, 5, 14),
            start_time=time(9, 0),
            end_time=time(17, 30),
            unpaid_break_hours=0.5,
        )

        self.assertEqual(calculate_paid_hours(entry), 8.0)
        self.assertTrue(is_public_holiday(entry.work_date))

    def test_public_holiday_list_contains_nine_statutory_holidays(self):
        self.assertFalse(is_public_holiday(date(2026, 1, 2)))
        self.assertFalse(is_public_holiday(date(2026, 3, 2)))
        self.assertEqual(len(PUBLIC_HOLIDAYS_2026), 9)

    def test_unpaid_work_entry_has_no_paid_hours(self):
        entry = WorkEntry(
            work_date=date(2026, 5, 15),
            start_time=time(9, 0),
            end_time=time(17, 0),
            unpaid_break_hours=1.0,
            paid=False,
        )

        self.assertEqual(calculate_paid_hours(entry), 0.0)
        self.assertFalse(is_public_holiday(entry.work_date))

    def test_monthly_hours_derive_public_holiday_hours_from_entries(self):
        entries = [
            WorkEntry(
                work_date=date(2026, 5, 14),
                start_time=time(9, 0),
                end_time=time(13, 0),
            ),
            WorkEntry(
                work_date=date(2026, 5, 15),
                start_time=time(9, 0),
                end_time=time(13, 0),
            ),
        ]

        self.assertEqual(calculate_monthly_hours(entries), (4.0, 4.0))

    def test_calculate_gross_wage_invalid_input(self):
        """Test invalid input handling for gross wage calculation."""
        with self.assertRaises(InvalidPayrollInputError):
            calculate_gross_wage(hours_worked=-1, hourly_wage=25.0)
        with self.assertRaises(InvalidPayrollInputError):
            calculate_gross_wage(hours_worked=160, hourly_wage=-25.0)
        with self.assertRaises(InvalidPayrollInputError):
            calculate_gross_wage(hours_worked=160, hourly_wage=25.0, holiday_hours=-8)

    def test_calculate_employee_deductions(self):
        """Test employee deduction calculations."""
        # Employee with weekly hours >= 8 (NBU applies)
        ahv, alv, tax, nbu = calculate_employee_deductions(
            gross_wage=4000.0,
            weekly_hours=10
        )
        self.assertAlmostEqual(ahv, 212.0)    # 4000 * 0.053
        self.assertAlmostEqual(alv, 44.0)     # 4000 * 0.011
        self.assertAlmostEqual(tax, 200.0)    # 4000 * 0.05
        self.assertAlmostEqual(nbu, 57.28)    # 4000 * 0.01432

        # Employee with weekly hours < 8 (NBU does not apply)
        ahv, alv, tax, nbu = calculate_employee_deductions(
            gross_wage=4000.0,
            weekly_hours=5
        )
        self.assertAlmostEqual(nbu, 0.0)      # NBU not applied

    def test_calculate_employer_costs(self):
        """Test employer cost calculations."""
        employer_ahv, employer_alv, employer_fak, employer_bu, admin_charge = calculate_employer_costs(
            gross_wage=4000.0
        )
        self.assertAlmostEqual(employer_ahv, 212.0)      # 4000 * 0.053
        self.assertAlmostEqual(employer_alv, 44.0)       # 4000 * 0.011
        self.assertAlmostEqual(employer_fak, 66.0)       # 4000 * 0.0165
        self.assertAlmostEqual(employer_bu, 20.2)       # 4000 * 0.00505
        self.assertAlmostEqual(admin_charge, 10.6)      # 212 * 0.05

    def test_generate_payslip(self):
        """Test payslip generation."""
        monthly_record = MonthlyRecord(
            id=1,
            employment_id=1,
            month=10,
            year=2026,
            hours_worked=160,
            holiday_hours=8,
            public_holiday_hours=4,
            cash_bonus=100,
            expense_reimbursements=50
        )

        payslip = generate_payslip(
            monthly_record=monthly_record,
            employment=self.employment
        )

        # Gross wage: (160 + 8 + 4) * 25 + (4 * 25 * 0.5) + 100 = 4450
        self.assertEqual(payslip.gross_wage, 4450.0)

        # Employee deductions
        self.assertAlmostEqual(payslip.ahv_deduction, 235.85)    # 4450 * 0.053
        self.assertAlmostEqual(payslip.alv_deduction, 48.95)     # 4450 * 0.011
        self.assertAlmostEqual(payslip.tax_deduction, 222.50)    # 4450 * 0.05
        self.assertAlmostEqual(payslip.nbu_deduction, 63.72)     # 4450 * 0.01432

        # Net payout uses rounded deductions: 4450 - (235.85 + 48.95 + 222.50 + 63.72) + 50 = 3928.98
        self.assertAlmostEqual(payslip.net_payout, 3928.98)

        # Employer costs
        self.assertAlmostEqual(payslip.employer_ahv, 235.85)     # 4450 * 0.053
        self.assertAlmostEqual(payslip.employer_alv, 48.95)      # 4450 * 0.011
        self.assertAlmostEqual(payslip.employer_fak, 73.43)      # 4450 * 0.0165
        self.assertAlmostEqual(payslip.employer_bu, 22.47)       # 4450 * 0.00505
        self.assertAlmostEqual(payslip.admin_charge, 11.79)      # 235.85 * 0.05

        # Total uses rounded employer cost lines: 4450 + 235.85 + 48.95 + 73.43 + 22.47 + 11.79 + 50 = 4892.49
        self.assertAlmostEqual(payslip.total_employer_cost, 4892.49)

    def test_validate_annual_limits(self):
        """Reject payroll runs that exceed employee or employer annual limits."""
        validate_annual_limits(
            self.employment,
            current_gross_wage=4000.0,
            employee_gross_to_date=18000.0,
            employer_gross_to_date=50000.0,
        )

        with self.assertRaises(AnnualLimitExceededError):
            validate_annual_limits(
                self.employment,
                current_gross_wage=5000.0,
                employee_gross_to_date=18000.0,
                employer_gross_to_date=50000.0,
            )

        with self.assertRaises(AnnualLimitExceededError):
            validate_annual_limits(
                self.employment,
                current_gross_wage=11000.0,
                employee_gross_to_date=10000.0,
                employer_gross_to_date=50000.0,
            )


if __name__ == "__main__":
    unittest.main()
