# tests/unit/test_monthly_record.py

import unittest

from src.app.domain.constants import RULES_YEAR
from src.app.domain.monthly_record import MonthlyRecord


class TestMonthlyRecordYear(unittest.TestCase):
    """Payroll is supported for the RULES_YEAR only (2026 AKBS rules)."""

    def test_rules_year_is_accepted(self):
        self.assertEqual(MonthlyRecord(year=RULES_YEAR).year, RULES_YEAR)

    def test_other_years_are_rejected(self):
        for year in (RULES_YEAR - 1, RULES_YEAR + 1):
            with self.subTest(year=year):
                with self.assertRaises(ValueError):
                    MonthlyRecord(year=year)


if __name__ == "__main__":
    unittest.main()
