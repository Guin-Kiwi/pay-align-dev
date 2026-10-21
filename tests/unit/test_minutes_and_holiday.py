# tests/unit/test_minutes_and_holiday.py

import json
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from src.app.domain.errors import InvalidPayrollInputError
from src.app.domain.holiday_balance import (
    contract_days_in_year,
    holiday_entitlement_minutes,
    remaining_holiday_minutes,
)
from src.app.domain.hour_categories import HourCategory, MinuteTotals, sum_minutes_by_category
from src.app.domain.payroll_calculation import calculate_gross_wage_from_minutes, nbu_applies

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "payroll_golden_cases.json"


def to_minutes(hours: str) -> int:
    minutes = Decimal(hours) * 60
    assert minutes == minutes.to_integral_value()
    return int(minutes)


class TestMinuteTotals(unittest.TestCase):
    def test_sums_by_category(self):
        totals = sum_minutes_by_category([
            (HourCategory.WORKED, 120),
            (HourCategory.WORKED, 30),
            (HourCategory.ANNUAL_HOLIDAY_TAKEN, 60),
            (HourCategory.PUBLIC_HOLIDAY_WORKED, 45),
            (HourCategory.PUBLIC_HOLIDAY_TAKEN, 15),
        ])
        self.assertEqual(totals, MinuteTotals(150, 45, 60, 15))
        self.assertEqual(totals.total, 270)

    def test_rejects_negative_and_non_integer(self):
        with self.assertRaises(InvalidPayrollInputError):
            MinuteTotals(worked=-1)
        with self.assertRaises(InvalidPayrollInputError):
            MinuteTotals(worked=1.5)
        with self.assertRaises(InvalidPayrollInputError):
            sum_minutes_by_category([(HourCategory.WORKED, -5)])


class TestGrossWageFromMinutes(unittest.TestCase):
    def test_golden_cases_gross_wage(self):
        cases = json.loads(FIXTURE.read_text())["cases"]
        for case in cases:
            with self.subTest(case=case["id"]):
                inp = case["input"]
                totals = MinuteTotals(
                    worked=to_minutes(inp["hours_worked"]),
                    public_holiday_worked=to_minutes(inp["public_holiday_hours"]),
                    annual_holiday_taken=to_minutes(inp["holiday_hours"]),
                )
                gross = calculate_gross_wage_from_minutes(
                    totals,
                    Decimal(case["employment"]["hourly_wage"]),
                    Decimal(inp["cash_bonus"]),
                )
                self.assertEqual(str(gross), case["expected"]["gross_wage"])

    def test_public_holiday_premium_and_leave(self):
        # 60 min worked on a public holiday = 1.5 h pay; leave = 1 h pay
        wage = Decimal("30.00")
        self.assertEqual(
            calculate_gross_wage_from_minutes(MinuteTotals(public_holiday_worked=60), wage),
            Decimal("45.00"),
        )
        self.assertEqual(
            calculate_gross_wage_from_minutes(MinuteTotals(public_holiday_taken=60), wage),
            Decimal("30.00"),
        )

    def test_rounds_half_up_once(self):
        # 1 minute at CHF 22.50/h = 0.375 -> 0.38 (half-up, not banker's)
        self.assertEqual(
            calculate_gross_wage_from_minutes(MinuteTotals(worked=1), Decimal("22.50")),
            Decimal("0.38"),
        )
        # 1 minute at CHF 30.30/h = 0.505 -> 0.51
        self.assertEqual(
            calculate_gross_wage_from_minutes(MinuteTotals(worked=1), Decimal("30.30")),
            Decimal("0.51"),
        )

    def test_rejects_float_and_negative(self):
        with self.assertRaises(InvalidPayrollInputError):
            calculate_gross_wage_from_minutes(MinuteTotals(worked=60), 25.0)
        with self.assertRaises(InvalidPayrollInputError):
            calculate_gross_wage_from_minutes(MinuteTotals(worked=60), Decimal("-1"))
        with self.assertRaises(InvalidPayrollInputError):
            calculate_gross_wage_from_minutes(MinuteTotals(worked=60), Decimal("25"), Decimal("-1"))


class TestNbuThreshold(unittest.TestCase):
    def test_threshold_is_480_minutes(self):
        self.assertFalse(nbu_applies(479))
        self.assertTrue(nbu_applies(480))
        self.assertTrue(nbu_applies(600))


class TestHolidayEntitlement(unittest.TestCase):
    def test_full_year(self):
        self.assertEqual(holiday_entitlement_minutes(4, 600, date(2026, 1, 1)), 2400)
        self.assertEqual(holiday_entitlement_minutes(5, 390, date(2026, 1, 1)), 1950)

    def test_start_before_2026_counts_full_year(self):
        self.assertEqual(holiday_entitlement_minutes(4, 600, date(2025, 6, 1)), 2400)

    def test_contract_days_inclusive(self):
        self.assertEqual(contract_days_in_year(date(2026, 1, 1)), 365)
        self.assertEqual(contract_days_in_year(date(2026, 12, 31)), 1)
        self.assertEqual(contract_days_in_year(date(2026, 3, 1), date(2026, 3, 1)), 1)
        self.assertEqual(contract_days_in_year(date(2026, 7, 1), date(2026, 12, 31)), 184)

    def test_pro_rata_rounds_to_nearest_minute(self):
        # 4 x 600 x 184 / 365 = 1209.86 -> 1210
        self.assertEqual(holiday_entitlement_minutes(4, 600, date(2026, 7, 1)), 1210)
        # 4 x 73 x 1 / 365 = 0.8 -> 1
        self.assertEqual(holiday_entitlement_minutes(4, 73, date(2026, 12, 31)), 1)
        # 4 x 90 x 1 / 365 = 0.986 -> 1; 4 x 45 x 1 / 365 = 0.49 -> 0
        self.assertEqual(holiday_entitlement_minutes(4, 90, date(2026, 12, 31)), 1)
        self.assertEqual(holiday_entitlement_minutes(4, 45, date(2026, 12, 31)), 0)
        # 365 is odd, so a value of exactly x.5 cannot occur; half-up is still
        # implemented as (2n + 365) // 730 and never rounds a .49 up.

    def test_end_date_in_year(self):
        # 1 Jan - 31 Mar = 90 days: 4 x 600 x 90 / 365 = 591.78 -> 592
        self.assertEqual(
            holiday_entitlement_minutes(4, 600, date(2026, 1, 1), date(2026, 3, 31)), 592
        )

    def test_rejects_invalid_input(self):
        with self.assertRaises(InvalidPayrollInputError):
            holiday_entitlement_minutes(3, 600, date(2026, 1, 1))
        with self.assertRaises(InvalidPayrollInputError):
            holiday_entitlement_minutes(4, 0, date(2026, 1, 1))
        with self.assertRaises(InvalidPayrollInputError):
            holiday_entitlement_minutes(4, 600.5, date(2026, 1, 1))
        with self.assertRaises(InvalidPayrollInputError):
            holiday_entitlement_minutes(4, 600, date(2026, 5, 2), date(2026, 5, 1))
        with self.assertRaises(InvalidPayrollInputError):
            holiday_entitlement_minutes(4, 600, date(2027, 1, 1))


class TestRemainingBalance(unittest.TestCase):
    def test_subtracts_taken_minutes(self):
        self.assertEqual(remaining_holiday_minutes(2400, 480), 1920)
        self.assertEqual(remaining_holiday_minutes(1920, 1920), 0)

    def test_first_run_uses_entitlement(self):
        entitlement = holiday_entitlement_minutes(4, 600, date(2026, 1, 1))
        self.assertEqual(remaining_holiday_minutes(entitlement, 0), 2400)

    def test_rejects_negative_result_and_bad_input(self):
        with self.assertRaises(InvalidPayrollInputError):
            remaining_holiday_minutes(100, 101)
        with self.assertRaises(InvalidPayrollInputError):
            remaining_holiday_minutes(-1, 0)
        with self.assertRaises(InvalidPayrollInputError):
            remaining_holiday_minutes(100, -1)
        with self.assertRaises(InvalidPayrollInputError):
            remaining_holiday_minutes(100.0, 10)


if __name__ == "__main__":
    unittest.main()
