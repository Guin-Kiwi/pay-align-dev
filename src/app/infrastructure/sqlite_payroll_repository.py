import sqlite3

from src.app.domain.monthly_record import MonthlyRecord
from src.app.domain.payslip import Payslip


class SQLitePayrollRepository:
    """Persist monthly payroll records and payslips in SQLite."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.connection.row_factory = sqlite3.Row
        self._create_schema()

    def _create_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS monthly_records (
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
            CREATE TABLE IF NOT EXISTS payslips (
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
            """
        )
        self.connection.commit()

    def save_monthly_record(self, record: MonthlyRecord, employer_id: int) -> MonthlyRecord:
        cursor = self.connection.execute(
            """
            INSERT INTO monthly_records (
                employment_id, employer_id, month, year, hours_worked,
                holiday_hours, public_holiday_hours, cash_bonus,
                expense_reimbursements
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.employment_id,
                employer_id,
                record.month,
                record.year,
                record.hours_worked,
                record.holiday_hours,
                record.public_holiday_hours,
                record.cash_bonus,
                record.expense_reimbursements,
            ),
        )
        self.connection.commit()
        record.id = cursor.lastrowid
        return record

    def get_monthly_record(self, record_id: int) -> MonthlyRecord:
        row = self.connection.execute(
            "SELECT * FROM monthly_records WHERE id = ?", (record_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"Monthly record {record_id} not found.")
        return MonthlyRecord(
            id=row["id"],
            employment_id=row["employment_id"],
            month=row["month"],
            year=row["year"],
            hours_worked=row["hours_worked"],
            holiday_hours=row["holiday_hours"],
            public_holiday_hours=row["public_holiday_hours"],
            cash_bonus=row["cash_bonus"],
            expense_reimbursements=row["expense_reimbursements"],
        )

    def save_payslip(self, payslip: Payslip) -> Payslip:
        cursor = self.connection.execute(
            """
            INSERT INTO payslips (
                monthly_record_id, gross_wage, ahv_deduction, alv_deduction,
                tax_deduction, nbu_deduction, net_payout, employer_ahv,
                employer_alv, employer_fak, employer_bu, admin_charge,
                total_employer_cost
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payslip.monthly_record_id,
                payslip.gross_wage,
                payslip.ahv_deduction,
                payslip.alv_deduction,
                payslip.tax_deduction,
                payslip.nbu_deduction,
                payslip.net_payout,
                payslip.employer_ahv,
                payslip.employer_alv,
                payslip.employer_fak,
                payslip.employer_bu,
                payslip.admin_charge,
                payslip.total_employer_cost,
            ),
        )
        self.connection.commit()
        payslip.id = cursor.lastrowid
        return payslip

    def get_payslip(self, monthly_record_id: int) -> Payslip:
        row = self.connection.execute(
            "SELECT * FROM payslips WHERE monthly_record_id = ?",
            (monthly_record_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Payslip for monthly record {monthly_record_id} not found.")
        return Payslip(**dict(row))

    def employee_gross_to_date(self, employment_id: int, year: int) -> float:
        row = self.connection.execute(
            """
            SELECT COALESCE(SUM(p.gross_wage), 0) AS total
            FROM payslips p
            JOIN monthly_records r ON r.id = p.monthly_record_id
            WHERE r.employment_id = ? AND r.year = ?
            """,
            (employment_id, year),
        ).fetchone()
        return float(row["total"])

    def employer_gross_to_date(self, employer_id: int, year: int) -> float:
        row = self.connection.execute(
            """
            SELECT COALESCE(SUM(p.gross_wage), 0) AS total
            FROM payslips p
            JOIN monthly_records r ON r.id = p.monthly_record_id
            WHERE r.employer_id = ? AND r.year = ?
            """,
            (employer_id, year),
        ).fetchone()
        return float(row["total"])