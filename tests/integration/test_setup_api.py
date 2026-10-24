import unittest

import pytest
from fastapi.testclient import TestClient

from src.app.infrastructure.database import DatabaseConfigurationError
from src.app.infrastructure.in_memory_setup_repository import InMemorySetupRepository
from src.app.infrastructure.web.app import create_app

EMPLOYER = {
    "name": "Anna Muster",
    "address": "Freie Strasse 1, 4001 Basel",
    "ahv_number": "756.1234.5678.97",
    "contact_info": "anna.muster@example.ch",
}
EMPLOYEE = {
    "name": "Maria Rossi",
    "address": "Clarastrasse 10, 4058 Basel",
    "ahv_number": "756.9876.5432.10",
    "nationality": "Italy",
}
EMPLOYMENT = {"start_date": "2026-01-01", "hourly_wage": 28.50, "weekly_hours": "6:00"}


def set_up_fresh(**employment):
    repository = InMemorySetupRepository()
    client = TestClient(create_app(setup_repository=repository))
    response = client.post(
        "/api/v1/setup",
        json={"employer": EMPLOYER, "employee": EMPLOYEE, "employment": {**EMPLOYMENT, **employment}},
    )
    return response, repository


def test_setup_survives_a_restart(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'payroll.db'}")
    with TestClient(create_app()) as client:
        client.post("/api/v1/setup", json={"employer": EMPLOYER, "employee": EMPLOYEE, "employment": EMPLOYMENT})

    with TestClient(create_app()) as client:
        assert client.get("/api/v1/employer").json() == {"id": 1, **EMPLOYER}


def test_app_does_not_start_without_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(DatabaseConfigurationError, match="DATABASE_URL"):
        create_app()


class TestSetupApi(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_app(setup_repository=InMemorySetupRepository()))

    def set_up(self, **body):
        return self.client.post("/api/v1/setup", json=body)

    def test_employer_is_not_found_before_setup(self):
        response = self.client.get("/api/v1/employer")

        self.assertEqual(response.status_code, 404)

    def test_setup_saves_all_three_and_confirms(self):
        response = self.set_up(employer=EMPLOYER, employee=EMPLOYEE, employment=EMPLOYMENT)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.json(),
            {
                "message": "Employment set up successfully",
                "employer_id": 1,
                "employee_id": 1,
                "employment_id": 1,
            },
        )
        employer = self.client.get("/api/v1/employer")
        self.assertEqual(employer.status_code, 200)
        self.assertEqual(employer.json(), {"id": 1, **EMPLOYER})

    def test_second_setup_links_to_the_existing_employer(self):
        self.set_up(employer=EMPLOYER, employee=EMPLOYEE, employment=EMPLOYMENT)

        response = self.set_up(
            employee={**EMPLOYEE, "ahv_number": "756.1111.2222.33"}, employment=EMPLOYMENT
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["employer_id"], 1)
        self.assertEqual(response.json()["employee_id"], 2)

    def test_second_setup_for_a_saved_ahv_number_reuses_the_employee(self):
        self.set_up(employer=EMPLOYER, employee=EMPLOYEE, employment=EMPLOYMENT)

        response = self.set_up(employee=EMPLOYEE, employment=EMPLOYMENT)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["employee_id"], 1)
        self.assertEqual(response.json()["employment_id"], 2)

    def test_sending_a_second_employer_is_a_conflict(self):
        self.set_up(employer=EMPLOYER, employee=EMPLOYEE, employment=EMPLOYMENT)

        response = self.set_up(employer=EMPLOYER, employee=EMPLOYEE, employment=EMPLOYMENT)

        self.assertEqual(response.status_code, 409)

    def test_invalid_ahv_number_is_rejected_and_nothing_is_saved(self):
        response = self.set_up(
            employer=EMPLOYER,
            employee={**EMPLOYEE, "ahv_number": "7561234567897"},
            employment=EMPLOYMENT,
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"], "Employee: Invalid AHV number format. Use 756.XXXX.XXXX.XX."
        )
        self.assertEqual(self.client.get("/api/v1/employer").status_code, 404)

    def test_employer_details_are_required_before_the_first_setup(self):
        response = self.set_up(employee=EMPLOYEE, employment=EMPLOYMENT)

        self.assertEqual(response.status_code, 400)

    def test_wage_of_exactly_22_20_is_accepted_as_number_or_text(self):
        for wage in (22.20, "22.20"):
            with self.subTest(wage=wage):
                client = TestClient(create_app(setup_repository=InMemorySetupRepository()))
                response = client.post(
                    "/api/v1/setup",
                    json={"employer": EMPLOYER, "employee": EMPLOYEE,
                          "employment": {**EMPLOYMENT, "hourly_wage": wage}},
                )
                self.assertEqual(response.status_code, 201)

    def test_wage_with_more_than_two_decimals_is_rejected(self):
        response = self.set_up(
            employer=EMPLOYER, employee=EMPLOYEE, employment={**EMPLOYMENT, "hourly_wage": "28.505"}
        )

        self.assertEqual(response.status_code, 422)

    def test_wage_up_to_500_is_accepted_and_above_is_rejected(self):
        for wage, status in (("500.00", 201), ("500.01", 400), ("30000000.00", 400)):
            with self.subTest(wage=wage):
                response, _ = set_up_fresh(hourly_wage=wage)
                self.assertEqual(response.status_code, status)
                if status == 400:
                    self.assertEqual(
                        response.json()["detail"],
                        f"Employment: Hourly wage (CHF {wage}) is above the maximum of CHF 500.00.",
                    )

    def test_nul_character_in_a_text_field_is_rejected_and_nothing_is_saved(self):
        response = self.set_up(
            employer=EMPLOYER, employee={**EMPLOYEE, "name": "Ma\x00ria"}, employment=EMPLOYMENT
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Employee: Name must not contain a NUL character.")
        self.assertEqual(self.client.get("/api/v1/employer").status_code, 404)

    def test_weekly_hours_typed_as_h_mm_are_accepted(self):
        for text, hours in (("6:30", 6.5), ("30:15", 30.25)):
            with self.subTest(text=text):
                response, repository = set_up_fresh(weekly_hours=text)
                self.assertEqual(response.status_code, 201)
                self.assertEqual(repository.employments[0].weekly_hours, hours)

    def test_weekly_hours_in_another_format_are_rejected_with_an_example(self):
        for text in ("6.5", "6,5", "6h30", "6:75", "6:5", "0:00", "1 hour 43 minutes", "٦:٣٠"):
            with self.subTest(text=text):
                response = self.set_up(
                    employer=EMPLOYER, employee=EMPLOYEE,
                    employment={**EMPLOYMENT, "weekly_hours": text},
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    response.json()["detail"],
                    "Employment: Invalid weekly hours. Use H:MM above 0:00, for example 6:30.",
                )
        self.assertEqual(self.client.get("/api/v1/employer").status_code, 404)

    def test_holiday_weeks_are_4_or_5_and_default_to_4(self):
        for weeks in (4, 5):
            with self.subTest(weeks=weeks):
                response, repository = set_up_fresh(holiday_weeks=weeks)
                self.assertEqual(response.status_code, 201)
                self.assertEqual(repository.employments[0].holiday_weeks, weeks)
        _, repository = set_up_fresh()
        self.assertEqual(repository.employments[0].holiday_weeks, 4)

    def test_other_holiday_weeks_are_rejected(self):
        for weeks in (3, 6, 20):
            with self.subTest(weeks=weeks):
                response, repository = set_up_fresh(holiday_weeks=weeks)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()["detail"], "Employment: Holiday weeks must be 4 or 5.")
                self.assertEqual(repository.employments, [])

    def test_end_date_is_optional_and_may_equal_the_start_date_or_fall_after_2026(self):
        for end_date in (None, "2026-01-01", "2027-08-31"):
            with self.subTest(end_date=end_date):
                response, repository = set_up_fresh(end_date=end_date)
                self.assertEqual(response.status_code, 201)
                saved = repository.employments[0].end_date
                self.assertEqual(saved and saved.isoformat(), end_date)

    def test_end_date_before_the_start_date_is_rejected(self):
        response, repository = set_up_fresh(start_date="2026-03-01", end_date="2026-02-28")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Employment: End date cannot be before the start date.")
        self.assertEqual(repository.employments, [])

    def test_start_date_must_be_in_2026(self):
        for start_date, status in (("2025-12-31", 400), ("2026-12-31", 201), ("2027-01-01", 400)):
            with self.subTest(start_date=start_date):
                response, _ = set_up_fresh(start_date=start_date)
                self.assertEqual(response.status_code, status)
        response, _ = set_up_fresh(start_date="2027-01-01")
        self.assertEqual(
            response.json()["detail"],
            "Employment: Start date must be in 2026; PayAlign has payroll rules for 2026 only.",
        )
