import sqlite3
from decimal import Decimal, ROUND_HALF_UP

from src.app.domain.monthly_record import MonthlyRecord
from src.app.domain.payslip import Payslip


class SQLitePayrollRepository:
    """Persist monthly payroll records and payslips in SQLite."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.connection.row_factory = sqlite3.Row
        self._create_schema()

    @staticmethod
    def _to_cents(value: float) -> int:
        return int(
            (Decimal(str(value)) * 100).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )

    @staticmethod
    def _from_cents(value: int) -> float:
        return value / 100

    def _create_schema(self) -> None:
        if self._is_legacy_schema():
            self._migrate_legacy_schema()
            return
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
                cash_bonus_cents INTEGER NOT NULL,
                expense_reimbursements_cents INTEGER NOT NULL,
                UNIQUE (employment_id, month, year)
            );
            CREATE TABLE IF NOT EXISTS payslips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                monthly_record_id INTEGER NOT NULL UNIQUE,
                gross_wage_cents INTEGER NOT NULL,
                ahv_deduction_cents INTEGER NOT NULL,
                alv_deduction_cents INTEGER NOT NULL,
                tax_deduction_cents INTEGER NOT NULL,
                nbu_deduction_cents INTEGER NOT NULL,
                net_payout_cents INTEGER NOT NULL,
                employer_ahv_cents INTEGER NOT NULL,
                employer_alv_cents INTEGER NOT NULL,
                employer_fak_cents INTEGER NOT NULL,
                employer_bu_cents INTEGER NOT NULL,
                admin_charge_cents INTEGER NOT NULL,
                total_employer_cost_cents INTEGER NOT NULL
            );
            """
        )
        self.connection.commit()

    def _is_legacy_schema(self) -> bool:
        tables = {
            row["name"]
            for row in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        if not {"monthly_records", "payslips"}.issubset(tables):
            return False
        monthly_columns = {
            row["name"]
            for row in self.connection.execute("PRAGMA table_info(monthly_records)")
        }
        return "cash_bonus" in monthly_columns

    def _migrate_legacy_schema(self) -> None:
        self.connection.execute("BEGIN")
        try:
            self.connection.executescript(
                """
                ALTER TABLE monthly_records RENAME TO monthly_records_legacy;
                ALTER TABLE payslips RENAME TO payslips_legacy;
                """
            )
            self._create_schema()
            self.connection.execute(
                """
                INSERT INTO monthly_records (
                    id, employment_id, employer_id, month, year, hours_worked,
                    holiday_hours, public_holiday_hours, cash_bonus_cents,
                    expense_reimbursements_cents
                )
                SELECT id, employment_id, employer_id, month, year, hours_worked,
                    holiday_hours, public_holiday_hours,
                    CAST(ROUND(cash_bonus * 100) AS INTEGER),
                    CAST(ROUND(expense_reimbursements * 100) AS INTEGER)
                FROM monthly_records_legacy
                """
            )
            money_columns = (
                "gross_wage", "ahv_deduction", "alv_deduction", "tax_deduction",
                "nbu_deduction", "net_payout", "employer_ahv", "employer_alv",
                "employer_fak", "employer_bu", "admin_charge", "total_employer_cost",
            )
            target_columns = ", ".join(f"{column}_cents" for column in money_columns)
            source_columns = ", ".join(
                f"CAST(ROUND({column} * 100) AS INTEGER)" for column in money_columns
            )
            self.connection.execute(
                f"INSERT INTO payslips (id, monthly_record_id, {target_columns}) "
                f"SELECT id, monthly_record_id, {source_columns} FROM payslips_legacy"
            )
            self.connection.executescript(
                """
                DROP TABLE monthly_records_legacy;
                DROP TABLE payslips_legacy;
                """
            )
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def save_monthly_record(self, record: MonthlyRecord, employer_id: int) -> MonthlyRecord:
        saved_record = self._insert_monthly_record(record, employer_id)
        self.connection.commit()
        return saved_record

    def _insert_monthly_record(self, record: MonthlyRecord, employer_id: int) -> MonthlyRecord:
        cursor = self.connection.execute(
            """
            INSERT INTO monthly_records (
                employment_id, employer_id, month, year, hours_worked,
                holiday_hours, public_holiday_hours, cash_bonus_cents,
                expense_reimbursements_cents
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
                self._to_cents(record.cash_bonus),
                self._to_cents(record.expense_reimbursements),
            ),
        )
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
            cash_bonus=self._from_cents(row["cash_bonus_cents"]),
            expense_reimbursements=self._from_cents(row["expense_reimbursements_cents"]),
        )

    def save_payslip(self, payslip: Payslip) -> Payslip:
        saved_payslip = self._insert_payslip(payslip)
        self.connection.commit()
        return saved_payslip

    def _insert_payslip(self, payslip: Payslip) -> Payslip:
        cursor = self.connection.execute(
            """
            INSERT INTO payslips (
                monthly_record_id, gross_wage_cents, ahv_deduction_cents,
                alv_deduction_cents, tax_deduction_cents, nbu_deduction_cents,
                net_payout_cents, employer_ahv_cents, employer_alv_cents,
                employer_fak_cents, employer_bu_cents, admin_charge_cents,
                total_employer_cost_cents
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payslip.monthly_record_id,
                self._to_cents(payslip.gross_wage),
                self._to_cents(payslip.ahv_deduction),
                self._to_cents(payslip.alv_deduction),
                self._to_cents(payslip.tax_deduction),
                self._to_cents(payslip.nbu_deduction),
                self._to_cents(payslip.net_payout),
                self._to_cents(payslip.employer_ahv),
                self._to_cents(payslip.employer_alv),
                self._to_cents(payslip.employer_fak),
                self._to_cents(payslip.employer_bu),
                self._to_cents(payslip.admin_charge),
                self._to_cents(payslip.total_employer_cost),
            ),
        )
        payslip.id = cursor.lastrowid
        return payslip

    def save_payroll_run(
        self, record: MonthlyRecord, payslip: Payslip, employer_id: int
    ) -> tuple[MonthlyRecord, Payslip]:
        """Persist a monthly record and payslip as one atomic transaction."""
        try:
            self.connection.execute("BEGIN")
            saved_record = self._insert_monthly_record(record, employer_id)
            payslip.monthly_record_id = saved_record.id
            saved_payslip = self._insert_payslip(payslip)
            self.connection.commit()
            return saved_record, saved_payslip
        except Exception:
            self.connection.rollback()
            raise

    def get_payslip(self, monthly_record_id: int) -> Payslip:
        row = self.connection.execute(
            "SELECT * FROM payslips WHERE monthly_record_id = ?",
            (monthly_record_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Payslip for monthly record {monthly_record_id} not found.")
        values = dict(row)
        for name in (
            "gross_wage", "ahv_deduction", "alv_deduction", "tax_deduction",
            "nbu_deduction", "net_payout", "employer_ahv", "employer_alv",
            "employer_fak", "employer_bu", "admin_charge", "total_employer_cost",
        ):
            values[name] = self._from_cents(values.pop(f"{name}_cents"))
        return Payslip(**values)

    # TODO(PR #3 review): limit is per employee, not per employment; needs employee_id. Owner: Ayla.
    def employee_gross_to_date(self, employment_id: int, year: int) -> float:
        row = self.connection.execute(
            """
            SELECT COALESCE(SUM(p.gross_wage_cents), 0) AS total
            FROM payslips p
            JOIN monthly_records r ON r.id = p.monthly_record_id
            WHERE r.employment_id = ? AND r.year = ?
            """,
            (employment_id, year),
        ).fetchone()
        return self._from_cents(row["total"])

    def employer_gross_to_date(self, employer_id: int, year: int) -> float:
        row = self.connection.execute(
            """
            SELECT COALESCE(SUM(p.gross_wage_cents), 0) AS total
            FROM payslips p
            JOIN monthly_records r ON r.id = p.monthly_record_id
            WHERE r.employer_id = ? AND r.year = ?
            """,
            (employer_id, year),
        ).fetchone()
        return self._from_cents(row["total"])