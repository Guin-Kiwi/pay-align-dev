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
