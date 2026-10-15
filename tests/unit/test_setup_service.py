import contextlib
import io
import unittest
from datetime import date

from src.app.application.setup_service import SetupService
from src.app.domain.employment import Employment


class TestSetupService(unittest.TestCase):
    def test_accepts_hourly_wage_of_22_50(self):
        employment = SetupService().create_employment(
            employer_id=1,
            employee_id=1,
            start_date=date(2026, 1, 1),
            hourly_wage=22.50,
            weekly_hours=10,
        )

        self.assertEqual(employment.hourly_wage, 22.50)

    def test_rejects_hourly_wage_of_22_19(self):
        with self.assertRaises(ValueError):
            SetupService().create_employment(
                employer_id=1,
                employee_id=1,
                start_date=date(2026, 1, 1),
                hourly_wage=22.19,
                weekly_hours=10,
            )

    def test_logs_warning_for_low_weekly_hours(self):
        with self.assertLogs("src.app.application.setup_service", level="WARNING") as logs:
            SetupService().create_employment(
                employer_id=1,
                employee_id=1,
                start_date=date(2026, 1, 1),
                hourly_wage=22.50,
                weekly_hours=4,
            )

        self.assertEqual(len(logs.records), 1)
        self.assertIn("Weekly hours (4)", logs.output[0])

    def test_does_not_warn_at_minimum_weekly_hours(self):
        with self.assertNoLogs("src.app.application.setup_service", level="WARNING"):
            SetupService().create_employment(
                employer_id=1,
                employee_id=1,
                start_date=date(2026, 1, 1),
                hourly_wage=22.50,
                weekly_hours=5,
            )


class TestEmployment(unittest.TestCase):
    def test_accepts_hourly_wage_at_minimum_of_22_20(self):
        employment = Employment(
            employer_id=1,
            employee_id=1,
            start_date=date(2026, 1, 1),
            hourly_wage=22.20,
            weekly_hours=10,
        )

        self.assertEqual(employment.hourly_wage, 22.20)

    def test_rejects_hourly_wage_below_minimum(self):
        with self.assertRaises(ValueError):
            Employment(
                employer_id=1,
                employee_id=1,
                start_date=date(2026, 1, 1),
                hourly_wage=22.19,
                weekly_hours=10,
            )

    def test_does_not_print_for_low_weekly_hours(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            Employment(
                employer_id=1,
                employee_id=1,
                start_date=date(2026, 1, 1),
                hourly_wage=22.50,
                weekly_hours=4,
            )

        self.assertEqual(output.getvalue(), "")
