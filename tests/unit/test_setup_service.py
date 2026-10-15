import contextlib
import io
import unittest
from datetime import date

from src.app.application.setup_service import SetupService
from src.app.domain.employee import Employee
from src.app.domain.employer import Employer
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


def make_employer(ahv_number):
    return Employer(
        name="Anna Muster",
        address="Freie Strasse 1, 4001 Basel",
        ahv_number=ahv_number,
        contact_info="anna.muster@example.ch",
    )


def make_employee(ahv_number):
    return Employee(
        name="Maria Rossi",
        address="Clarastrasse 10, 4058 Basel",
        ahv_number=ahv_number,
        nationality="Italy",
    )


class TestAhvNumber(unittest.TestCase):
    VALID = "756.1234.5678.97"
    INVALID = {
        "no dots": "7561234567897",
        "does not start with 756": "123.4567.8901.23",
        "dots in the wrong place": "756.12345.678.97",
        "too short": "756.1234.5678.9",
        "spaces instead of dots": "756 1234 5678 97",
    }

    def test_accepts_dotted_ahv_number(self):
        self.assertEqual(make_employer(self.VALID).ahv_number, self.VALID)
        self.assertEqual(make_employee(self.VALID).ahv_number, self.VALID)

    def test_employer_rejects_invalid_ahv_numbers(self):
        for case, ahv_number in self.INVALID.items():
            with self.subTest(case=case), self.assertRaises(ValueError):
                make_employer(ahv_number)

    def test_employee_rejects_invalid_ahv_numbers(self):
        for case, ahv_number in self.INVALID.items():
            with self.subTest(case=case), self.assertRaises(ValueError):
                make_employee(ahv_number)

    def test_error_message_shows_the_expected_format(self):
        with self.assertRaisesRegex(ValueError, r"756\.XXXX\.XXXX\.XX"):
            make_employee("7561234567897")
