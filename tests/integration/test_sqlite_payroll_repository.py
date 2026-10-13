import sqlite3
import unittest
from datetime import date, time

from src.app.application.payroll_service import PayrollService
from src.app.domain.monthly_record import MonthlyRecord
from src.app.domain.payslip import Payslip
from src.app.domain.work_entry import WorkEntry
from src.app.domain.employment import Employment
from src.app.infrastructure.sqlite_payroll_repository import SQLitePayrollRepository


class TestSQLitePayrollRepository(unittest.TestCase):
    def test_migrates_legacy_real_money_columns_to_cents(self):
        connection = sqlite3.connect(":memory:")
        connection.executescript(
            """
            CREATE TABLE monthly_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employment_id INTEGER NOT NULL,
                employer_id INTEGER NOT NULL,
                month INTEGER NOT NULL,
                year INTEGER NOT NULL,
                hours_worked REAL NOT NULL,
                holiday_hours REAL NOT NULL,
                public_holiday_hours REAL NOT NULL,
                cash_bonus REAL NOT NULL,
                expense_reimbursements REAL NOT NULL
            );
            CREATE TABLE payslips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                monthly_record_id INTEGER NOT NULL UNIQUE,
                gross_wage REAL NOT NULL,
                ahv_deduction REAL NOT NULL,
                alv_deduction REAL NOT NULL,
                tax_deduction REAL NOT NULL,
                nbu_deduction REAL NOT NULL,
                net_payout REAL NOT NULL,
                employer_ahv REAL NOT NULL,
                employer_alv REAL NOT NULL,
                employer_fak REAL NOT NULL,
                employer_bu REAL NOT NULL,
                admin_charge REAL NOT NULL,
                total_employer_cost REAL NOT NULL
            );
            INSERT INTO monthly_records VALUES
                (1, 7, 3, 10, 2026, 10, 0, 0, 12.34, 1.23);
            INSERT INTO payslips VALUES
                (1, 1, 250.01, 13.25, 2.75, 12.50, 0, 222.74,
                 13.25, 2.75, 4.13, 1.26, 0.66, 272.06);
            """
        )

        repository = SQLitePayrollRepository(connection)

        self.assertEqual(repository.get_monthly_record(1).cash_bonus, 12.34)
        self.assertEqual(repository.get_payslip(1).gross_wage, 250.01)

    def test_rejects_duplicate_monthly_payroll_for_employment(self):
        connection = sqlite3.connect(":memory:")
        repository = SQLitePayrollRepository(connection)
        record = MonthlyRecord(employment_id=7, month=10, year=2026, hours_worked=10)

        repository.save_monthly_record(record, employer_id=3)
        with self.assertRaises(sqlite3.IntegrityError):
            repository.save_monthly_record(
                MonthlyRecord(employment_id=7, month=10, year=2026, hours_worked=8),
                employer_id=3,
            )

    def test_payroll_run_rolls_back_when_payslip_save_fails(self):
        connection = sqlite3.connect(":memory:")
        repository = SQLitePayrollRepository(connection)
        record = MonthlyRecord(employment_id=7, month=10, year=2026, hours_worked=10)
        payslip = Payslip(monthly_record_id=0, gross_wage=250.0, net_payout=200.0)

        original_insert_payslip = repository._insert_payslip

        def fail_after_insert(value):
            original_insert_payslip(value)
            raise RuntimeError("simulated payslip failure")

        repository._insert_payslip = fail_after_insert
        with self.assertRaises(RuntimeError):
            repository.save_payroll_run(record, payslip, employer_id=3)

        self.assertEqual(
            connection.execute("SELECT COUNT(*) FROM monthly_records").fetchone()[0],
            0,
        )

    def test_payroll_service_processes_and_persists_monthly_payroll(self):
        connection = sqlite3.connect(":memory:")
        repository = SQLitePayrollRepository(connection)
        service = PayrollService()
        employment = Employment(
            id=7,
            employer_id=3,
            employee_id=9,
            hourly_wage=25.0,
            weekly_hours=10.0,
        )

        record, payslip = service.process_monthly_payroll(
            repository=repository,
            employment=employment,
            month=10,
            year=2026,
            hours_worked=10.0,
        )

        self.assertEqual(record.id, payslip.monthly_record_id)
        self.assertEqual(payslip.gross_wage, 250.0)
        self.assertEqual(repository.employee_gross_to_date(7, 2026), 250.0)
        self.assertEqual(repository.employer_gross_to_date(3, 2026), 250.0)

    def test_payroll_service_derives_hours_from_work_entries(self):
        connection = sqlite3.connect(":memory:")
        repository = SQLitePayrollRepository(connection)
        service = PayrollService()
        employment = Employment(
            id=8,
            employer_id=3,
            employee_id=10,
            hourly_wage=25.0,
            weekly_hours=10.0,
        )

        record, payslip = service.process_monthly_payroll(
            repository=repository,
            employment=employment,
            month=5,
            year=2026,
            work_entries=[
                WorkEntry(date(2026, 5, 14), time(9), time(13)),
                WorkEntry(date(2026, 5, 15), time(9), time(13)),
            ],
        )

        self.assertEqual(record.hours_worked, 4.0)
        self.assertEqual(record.public_holiday_hours, 4.0)
        self.assertEqual(payslip.gross_wage, 250.0)

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
