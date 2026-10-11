import sqlite3
import unittest

from src.app.domain.monthly_record import MonthlyRecord
from src.app.domain.payslip import Payslip
from src.app.infrastructure.sqlite_payroll_repository import SQLitePayrollRepository


class TestSQLitePayrollRepository(unittest.TestCase):
    def test_persists_payroll_and_calculates_year_to_date_gross(self):
        connection = sqlite3.connect(":memory:")
        repository = SQLitePayrollRepository(connection)
        record = MonthlyRecord(
            employment_id=7,
            month=10,
            year=2026,
            hours_worked=10,
        )
        payslip = Payslip(
            monthly_record_id=0,
            gross_wage=250.0,
            net_payout=200.0,
        )

        saved_record = repository.save_monthly_record(record, employer_id=3)
        payslip.monthly_record_id = saved_record.id
        saved_payslip = repository.save_payslip(payslip)

        loaded_record = repository.get_monthly_record(saved_record.id)
        loaded_payslip = repository.get_payslip(saved_record.id)

        self.assertEqual(loaded_record, saved_record)
        self.assertEqual(loaded_payslip, saved_payslip)
        self.assertEqual(
            repository.employee_gross_to_date(employment_id=7, year=2026),
            250.0,
        )
        self.assertEqual(
            repository.employer_gross_to_date(employer_id=3, year=2026),
            250.0,
        )


if __name__ == "__main__":
    unittest.main()
