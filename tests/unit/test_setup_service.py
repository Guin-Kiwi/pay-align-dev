import contextlib
import io
import unittest
from datetime import date
from decimal import Decimal
from unittest import mock

from src.app.application.ports.setup_repository import SetupResult
from src.app.application.setup_service import EmployerAlreadyExistsError, SetupService
from src.app.domain.employee import Employee
from src.app.domain.employer import Employer
from src.app.domain.employment import Employment
from src.app.infrastructure.in_memory_setup_repository import InMemorySetupRepository


class TestSetupService(unittest.TestCase):
    def setUp(self):
        self.service = SetupService(InMemorySetupRepository())

    def test_accepts_hourly_wage_of_22_50(self):
        employment = self.service.create_employment(
            employer_id=1,
            employee_id=1,
            start_date=date(2026, 1, 1),
            hourly_wage=22.50,
            weekly_hours=10,
        )

        self.assertEqual(employment.hourly_wage, 22.50)

    def test_rejects_hourly_wage_of_22_19(self):
        with self.assertRaises(ValueError):
            self.service.create_employment(
                employer_id=1,
                employee_id=1,
                start_date=date(2026, 1, 1),
                hourly_wage=22.19,
                weekly_hours=10,
            )

    def test_logs_warning_for_low_weekly_hours(self):
        with self.assertLogs("src.app.application.setup_service", level="WARNING") as logs:
            self.service.create_employment(
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
            self.service.create_employment(
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

    def test_minimum_wage_check_is_exact_with_a_decimal_minimum(self):
        with mock.patch("src.app.domain.employment.MIN_HOURLY_WAGE", Decimal("22.20")):
            for wage in (22.20, Decimal("22.20")):
                with self.subTest(wage=wage):
                    employment = Employment(
                        employer_id=1, employee_id=1, start_date=date(2026, 1, 1),
                        hourly_wage=wage, weekly_hours=10,
                    )
                    self.assertEqual(employment.hourly_wage, wage)
            with self.assertRaises(ValueError):
                Employment(
                    employer_id=1, employee_id=1, start_date=date(2026, 1, 1),
                    hourly_wage=Decimal("22.19"), weekly_hours=10,
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


def make_employer(ahv_number="756.1234.5678.97", **overrides):
    fields = {
        "name": "Anna Muster",
        "address": "Freie Strasse 1, 4001 Basel",
        "ahv_number": ahv_number,
        "contact_info": "anna.muster@example.ch",
    }
    return Employer(**{**fields, **overrides})


def make_employee(ahv_number="756.9876.5432.10", **overrides):
    fields = {
        "name": "Maria Rossi",
        "address": "Clarastrasse 10, 4058 Basel",
        "ahv_number": ahv_number,
        "nationality": "Italy",
    }
    return Employee(**{**fields, **overrides})


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


class TestRequiredFields(unittest.TestCase):
    BLANK_VALUES = ["", "   "]

    def test_employer_requires_every_field(self):
        for field, label in [("name", "Name"), ("address", "Address"), ("contact_info", "Contact info")]:
            for value in self.BLANK_VALUES:
                with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, f"{label} is required"):
                    make_employer(**{field: value})

    def test_employee_requires_every_field(self):
        for field, label in [("name", "Name"), ("address", "Address"), ("nationality", "Nationality")]:
            for value in self.BLANK_VALUES:
                with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, f"{label} is required"):
                    make_employee(**{field: value})

    def test_ahv_number_is_required(self):
        with self.assertRaisesRegex(ValueError, "AHV number is required"):
            make_employer(ahv_number="")
        with self.assertRaisesRegex(ValueError, "AHV number is required"):
            make_employee(ahv_number="")


EMPLOYER_DETAILS = {
    "name": "Anna Muster",
    "address": "Freie Strasse 1, 4001 Basel",
    "ahv_number": "756.1234.5678.97",
    "contact_info": "anna.muster@example.ch",
}
EMPLOYEE_DETAILS = {
    "name": "Maria Rossi",
    "address": "Clarastrasse 10, 4058 Basel",
    "ahv_number": "756.9876.5432.10",
    "nationality": "Italy",
}
EMPLOYMENT_DETAILS = {
    "start_date": date(2026, 1, 1),
    "hourly_wage": 28.50,
    "weekly_hours": 6,
}


class TestSetUpEmployment(unittest.TestCase):
    def setUp(self):
        self.repository = InMemorySetupRepository()
        self.service = SetupService(self.repository)

    def test_saves_employer_employee_and_employment_when_no_employer_exists(self):
        result = self.service.set_up_employment(
            employer=EMPLOYER_DETAILS, employee=EMPLOYEE_DETAILS, employment=EMPLOYMENT_DETAILS
        )

        self.assertEqual(result, SetupResult(employer_id=1, employee_id=1, employment_id=1))
        self.assertEqual(self.repository.employer.name, "Anna Muster")
        self.assertEqual(self.repository.employees[0].name, "Maria Rossi")
        employment = self.repository.employments[0]
        self.assertEqual((employment.employer_id, employment.employee_id), (1, 1))

    def test_links_to_the_existing_employer(self):
        self.repository.employer = make_employer(id=7)

        result = self.service.set_up_employment(employee=EMPLOYEE_DETAILS, employment=EMPLOYMENT_DETAILS)

        self.assertEqual(result.employer_id, 7)
        self.assertEqual(self.repository.employments[0].employer_id, 7)

    def test_rejects_a_second_employer_and_saves_nothing(self):
        self.repository.employer = make_employer(id=7)

        with self.assertRaises(EmployerAlreadyExistsError):
            self.service.set_up_employment(
                employer=EMPLOYER_DETAILS, employee=EMPLOYEE_DETAILS, employment=EMPLOYMENT_DETAILS
            )

        self.assertEqual(self.repository.employees, [])

    def test_requires_employer_details_when_no_employer_exists(self):
        with self.assertRaisesRegex(ValueError, "^Employer: "):
            self.service.set_up_employment(employee=EMPLOYEE_DETAILS, employment=EMPLOYMENT_DETAILS)

        self.assertIsNone(self.repository.employer)
        self.assertEqual(self.repository.employees, [])

    def test_names_the_invalid_part_and_saves_nothing(self):
        cases = {
            "Employer": {
                "employer": {**EMPLOYER_DETAILS, "ahv_number": "7561234567897"},
                "employee": EMPLOYEE_DETAILS,
                "employment": EMPLOYMENT_DETAILS,
            },
            "Employee": {
                "employer": EMPLOYER_DETAILS,
                "employee": {**EMPLOYEE_DETAILS, "address": ""},
                "employment": EMPLOYMENT_DETAILS,
            },
            "Employment": {
                "employer": EMPLOYER_DETAILS,
                "employee": EMPLOYEE_DETAILS,
                "employment": {**EMPLOYMENT_DETAILS, "hourly_wage": 20.00},
            },
        }
        for part, arguments in cases.items():
            with self.subTest(part=part):
                with self.assertRaisesRegex(ValueError, f"^{part}: "):
                    self.service.set_up_employment(**arguments)

                self.assertIsNone(self.repository.employer)
                self.assertEqual(self.repository.employees, [])
                self.assertEqual(self.repository.employments, [])

    def test_get_employer_returns_the_saved_employer_or_none(self):
        self.assertIsNone(self.service.get_employer())

        self.repository.employer = make_employer(id=7)

        self.assertEqual(self.service.get_employer().id, 7)
