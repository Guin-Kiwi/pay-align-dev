# tests/unit/test_payroll_service.py

import unittest

from src.app.application.payroll_service import PayrollService
from src.app.domain.employment import Employment
from src.app.domain.errors import InvalidPayrollInputError


class TestPayrollService(unittest.TestCase):
    """Unit tests for PayrollService."""

    def setUp(self):
        """Set up test data."""
        self.service = PayrollService()
        self.employment = Employment(
            id=1,
            employer_id=1,
            employee_id=1,
            hourly_wage=25.0,
            weekly_hours=10
        )


    def test_create_monthly_record(self):
        """Test monthly record creation."""
        monthly_record = self.service.create_monthly_record(
            employment=self.employment,
            month=10,
            year=2026,
            hours_worked=160,
            holiday_hours=8,
            public_holiday_hours=4,
            cash_bonus=100,
            expense_reimbursements=50
        )
        self.assertEqual(monthly_record.employment_id, 1)
        self.assertEqual(monthly_record.month, 10)
        self.assertEqual(monthly_record.year, 2026)
        self.assertEqual(monthly_record.hours_worked, 160)
        self.assertEqual(monthly_record.holiday_hours, 8)
        self.assertEqual(monthly_record.public_holiday_hours, 4)
        self.assertEqual(monthly_record.cash_bonus, 100)
        self.assertEqual(monthly_record.expense_reimbursements, 50)

    def test_create_monthly_record_invalid_input(self):
        """Test invalid input handling for monthly record creation."""
        with self.assertRaises(InvalidPayrollInputError):
            self.service.create_monthly_record(
                employment=self.employment,
                month=10,
                year=2026,
                hours_worked=-160
            )


if __name__ == "__main__":
    unittest.main()
