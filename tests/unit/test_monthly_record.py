# tests/unit/test_monthly_record.py

import unittest

from src.app.domain.monthly_record import MonthlyRecord


class TestMonthlyRecordYear(unittest.TestCase):
    """Payroll is supported for 2026 only (2026 AKBS rules)."""

    def test_year_2026_is_accepted(self):
        self.assertEqual(MonthlyRecord(year=2026).year, 2026)

    def test_other_years_are_rejected(self):
        for year in (2025, 2027):
            with self.subTest(year=year):
                with self.assertRaises(ValueError):
                    MonthlyRecord(year=year)


if __name__ == "__main__":
    unittest.main()
