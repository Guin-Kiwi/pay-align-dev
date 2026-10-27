from fastapi.testclient import TestClient
from pathlib import Path
import subprocess

from src.app.infrastructure.web.app import create_app
from tests.integration.authenticated_client import AuthenticatedTestClient


def test_payslip_page_requires_login():
    response = TestClient(create_app()).get('/payslips', follow_redirects=False)
    assert response.status_code == 303
    assert response.headers['location'] == '/login'


def test_payslip_page_exposes_read_only_detail_and_assets():
    with AuthenticatedTestClient(create_app()) as client:
        response = client.get('/payslips')
        assert response.status_code == 200
        for label in ('Employee AHV number', 'Employee deductions', 'Expense reimbursements',
                      'Net payout due', 'Employer costs', 'Holiday balance'):
            assert label in response.text
        assert client.get('/setup-assets/payslip.js').status_code == 200
        assert client.get('/setup-assets/payslip.css').status_code == 200


def test_payslip_javascript_renders_saved_detail_and_handles_errors():
    root = Path(__file__).resolve().parents[2]
    subprocess.run(
        ['node', str(root / 'tests/fixtures/payslip_view.js'),
         str(root / 'src/app/interfaces/static/payslip.js')],
        check=True, timeout=20,
    )
