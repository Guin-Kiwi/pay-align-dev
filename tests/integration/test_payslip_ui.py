from fastapi.testclient import TestClient
from html.parser import HTMLParser
from pathlib import Path
import os
import re
import subprocess

from src.app.domain.constants import RULES_YEAR
from src.app.infrastructure.web.app import create_app
from tests.integration.authenticated_client import AuthenticatedTestClient
from tests.integration.page_scripts import script_paths


def test_payslip_page_requires_login():
    response = TestClient(create_app()).get('/payslips', follow_redirects=False)
    assert response.status_code == 303
    assert response.headers['location'] == '/login'


def test_payslip_page_is_named_for_the_payslip():
    with AuthenticatedTestClient(create_app()) as client:
        response = client.get('/payslips?employment_id=7&year=2026&month=4')
        assert response.status_code == 200
        assert '<title>Payslip | PayAlign</title>' in response.text
        assert '<h1>Payslip</h1>' in response.text
        assert 'data-current-route="/payslips"' in response.text


def test_payslip_page_exposes_read_only_detail_and_assets():
    with AuthenticatedTestClient(create_app()) as client:
        response = client.get('/payslips')
        assert response.status_code == 200
        for label in ('Employee AHV number', 'Employee deductions', 'Expense reimbursements',
                      'Net payout due', 'Employer costs', 'Holiday balance'):
            assert label in response.text
        class PrintSections(HTMLParser):
            def __init__(self):
                super().__init__()
                self.sections = {}

            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == 'section' and 'id' in attrs:
                    self.sections[attrs['id']] = attrs.get('class', '').split()

        sections = PrintSections()
        sections.feed(response.text)
        assert 'no-print' in sections.sections['employer-costs']
        assert '<button id="enter-timesheet" type="button" hidden>' in response.text
        assert response.text.index('id="enter-timesheet"') < response.text.index('class="payslip-workspace"')
        assert re.findall(r'<script src="([^"]+)"', response.text) == [
            '/setup-assets/navigation.js', '/setup-assets/common.js', '/setup-assets/payslip.js']
        assert '@media print' in client.get('/setup-assets/payslip.css').text
        assert '.no-print { display: none !important; }' in client.get('/setup-assets/payslip.css').text
        assert client.get('/setup-assets/payslip.js').status_code == 200
        assert client.get('/setup-assets/payslip.css').status_code == 200


def test_payslip_javascript_renders_saved_detail_and_handles_errors():
    root = Path(__file__).resolve().parents[2]
    subprocess.run(
        ['node', str(root / 'tests/fixtures/payslip_view.js'),
         *script_paths('payslip')],
        check=True, timeout=20, env={**os.environ, 'RULES_YEAR': str(RULES_YEAR)},
    )
