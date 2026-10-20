# tests/unit/test_payroll_golden.py
"""Golden payroll cases taken from the recalculated workbook (Payslip_2026.xlsm)."""

import json
import unittest
from decimal import Decimal
from pathlib import Path

from src.app.domain.employment import Employment
from src.app.domain.hour_categories import MinuteTotals
from src.app.domain.payroll_calculation import generate_payslip

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "payroll_golden_cases.json"
CASES = json.loads(FIXTURE.read_text())["cases"]

# Payslip attribute -> fixture key (net_payout on the payslip includes expense
# reimbursements, so it corresponds to the workbook's payment_to_employee).
PAYSLIP_FIELDS = {
    "gross_wage": "gross_wage",
    "ahv_deduction": "ahv_deduction",
    "alv_deduction": "alv_deduction",
    "tax_deduction": "tax_deduction",
    "nbu_deduction": "nbu_deduction",
    "net_payout": "payment_to_employee",
    "employer_ahv": "employer_ahv",
    "employer_alv": "employer_alv",
    "employer_fak": "employer_fak",
    "employer_bu": "employer_bu",
}
PENDING_FIELDS = ("admin_charge", "total_employer_cost")


def _money(value) -> Decimal:
    return Decimal(str(value))


def _minutes(hours: str) -> int:
    minutes = Decimal(hours) * 60
    assert minutes == minutes.to_integral_value()
    return int(minutes)


def _payslip_for(case):
    employment = Employment(
        id=1,
        employer_id=1,
        employee_id=1,
        hourly_wage=float(case["employment"]["hourly_wage"]),
        weekly_hours=float(case["employment"]["weekly_hours"]),
    )
    inputs = case["input"]
    totals = MinuteTotals(
        worked=_minutes(inputs["hours_worked"]),
        public_holiday_worked=_minutes(inputs["public_holiday_hours"]),
        annual_holiday_taken=_minutes(inputs["holiday_hours"]),
    )
    return generate_payslip(
        totals=totals,
        employment=employment,
        cash_bonus=_money(inputs["cash_bonus"]),
        expense_reimbursements=_money(inputs["expense_reimbursements"]),
    )


class TestPayrollGolden(unittest.TestCase):
    """Compare generate_payslip with the workbook for every golden case."""

    def test_payslip_lines_match_workbook(self):
        for case in CASES:
            with self.subTest(case=case["id"]):
                payslip = _payslip_for(case)
                expected = case["expected"]
                for attribute, key in PAYSLIP_FIELDS.items():
                    self.assertEqual(
                        _money(getattr(payslip, attribute)),
                        _money(expected[key]),
                        f"{case['id']}: {attribute}",
                    )

    def test_derived_totals_match_workbook(self):
        for case in CASES:
            with self.subTest(case=case["id"]):
                payslip = _payslip_for(case)
                expected = case["expected"]
                deductions = (
                    _money(payslip.ahv_deduction)
                    + _money(payslip.alv_deduction)
                    + _money(payslip.tax_deduction)
                    + _money(payslip.nbu_deduction)
                )
                self.assertEqual(deductions, _money(expected["total_employee_deductions"]))
                self.assertEqual(
                    _money(payslip.gross_wage) - deductions,
                    _money(expected["net_payout"]),
                )

    @unittest.expectedFailure
    def test_admin_charge_and_total_employer_cost_match_workbook(self):
        """Pending: the code uses gross x 5.3% x 5%, the workbook gross x 10.6% x 5%.

        Remove the expectedFailure decorator once the formula is agreed and fixed.
        """
        for case in CASES:
            payslip = _payslip_for(case)
            for attribute in PENDING_FIELDS:
                self.assertEqual(
                    _money(getattr(payslip, attribute)),
                    _money(case["expected"][attribute]),
                    f"{case['id']}: {attribute}",
                )


if __name__ == "__main__":
    unittest.main()
