import unittest
from datetime import date

from src.app.application.setup_service import SetupService


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
