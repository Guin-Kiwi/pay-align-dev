from fastapi.testclient import TestClient
from html.parser import HTMLParser
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
        assert '@media print' in client.get('/setup-assets/payslip.css').text
        assert '.no-print { display: none !important; }' in client.get('/setup-assets/payslip.css').text
        assert client.get('/setup-assets/payslip.js').status_code == 200
        assert client.get('/setup-assets/payslip.css').status_code == 200


def test_payslip_page_brand_and_nav_link_go_home_to_employments():
    class Anchors(HTMLParser):
        def __init__(self):
            super().__init__()
            self.anchors = []
            self._current = None

        def handle_starttag(self, tag, attrs):
            if tag == 'a':
                self._current = {**dict(attrs), 'text': ''}
                self.anchors.append(self._current)

        def handle_data(self, data):
            if self._current is not None:
                self._current['text'] += data

        def handle_endtag(self, tag):
            if tag == 'a':
                self._current = None

    with AuthenticatedTestClient(create_app()) as client:
        anchors = Anchors()
        anchors.feed(client.get('/payslips').text)
    brand = next(a for a in anchors.anchors if a.get('class') == 'brand')
    home = next(a for a in anchors.anchors if a['text'] == 'Home')
    assert brand['href'] == '/employments'
    assert home['href'] == '/employments'


def test_payslip_javascript_renders_saved_detail_and_handles_errors():
    root = Path(__file__).resolve().parents[2]
    subprocess.run(
        ['node', str(root / 'tests/fixtures/payslip_view.js'),
         str(root / 'src/app/interfaces/static/payslip.js')],
        check=True, timeout=20,
    )
