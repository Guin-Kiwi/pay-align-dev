from pathlib import Path

from fastapi.testclient import TestClient

from src.app.infrastructure.web.app import create_app
from tests.integration.authenticated_client import AuthenticatedTestClient
from tests.integration.page_scripts import node_binary, script_paths


def test_account_details_page_is_separate_and_authenticated():
    assert TestClient(create_app()).get('/account-details', follow_redirects=False).status_code == 303
    page = AuthenticatedTestClient(create_app()).get('/account-details')
    assert page.status_code == 200
    assert '<h1>Your account details</h1>' in page.text
    assert 'employee-name' not in page.text
    assert 'employment-heading' not in page.text
    assert '/setup-assets/common.js' in page.text
    assert '/setup-assets/account-details.js' in page.text


def test_account_details_javascript_saves_then_returns_home():
    import subprocess
    root = Path(__file__).resolve().parents[2]
    subprocess.run([node_binary(), str(root / 'tests/fixtures/account_details.js'),
                    *script_paths('account-details')], check=True, timeout=10)
