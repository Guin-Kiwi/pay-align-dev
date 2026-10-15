import unittest

from fastapi.testclient import TestClient

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
EMPLOYMENT = {"start_date": "2026-01-01", "hourly_wage": 28.50, "weekly_hours": 6}


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
