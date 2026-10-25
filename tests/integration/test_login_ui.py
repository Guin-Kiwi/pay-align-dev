from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

from src.app.infrastructure.web.app import create_app
from tests.integration.authenticated_client import TEST_PASSWORD, AuthenticatedTestClient

STATIC = Path(__file__).resolve().parents[2] / 'src' / 'app' / 'interfaces' / 'static'
FLOW = Path(__file__).resolve().parents[1] / 'fixtures' / 'login_flow.js'


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.tags = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))

    def by_id(self):
        return {attrs['id']: attrs for _, attrs in self.tags if 'id' in attrs}


def node_binary():
    node = shutil.which('node')
    if node is None:
        candidates = sorted(Path('/vscode/vscode-server/bin').glob('*/*/node'))
        assert candidates, 'The UI tests require Node.js.'
        node = str(candidates[-1])
    return node


def run_flow(scenario, email='anna@example.ch', password=TEST_PASSWORD):
    client = TestClient(create_app())
    page = Page(client.get('/login').text)
    result = subprocess.run(
        [node_binary(), str(FLOW)],
        input=json.dumps({
            'scenario': scenario, 'elements': page.by_id(),
            'javascript': client.get('/setup-assets/login.js').text,
            'credentials': {'email': email, 'password': password},
        }),
        text=True, capture_output=True, timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def replay(client, calls):
    token = None
    responses = []
    for call in calls:
        if call['url'] == '/api/v1/auth/csrf':
            response = client.get(call['url'])
            assert response.status_code == 200
            token = response.json()['csrf_token']
        else:
            headers = {
                name: token if name == 'X-CSRF-Token' else value
                for name, value in call['headers'].items()
            }
            response = client.request(call['method'], call['url'], headers=headers, content=call['body'])
        responses.append(response)
    return responses


def test_login_page_is_served_with_the_setup_page_styles():
    response = TestClient(create_app()).get('/login')
    assert response.status_code == 200
    assert response.headers['content-type'].startswith('text/html')
    page = Page(response.text)
    assert ('html', {'lang': 'en'}) in page.tags
    assert 'Log in' in response.text
    stylesheets = [attrs['href'] for tag, attrs in page.tags if tag == 'link' and attrs.get('rel') == 'stylesheet']
    assert stylesheets == ['/setup-assets/setup.css', '/setup-assets/login.css']
    scripts = [attrs for tag, attrs in page.tags if tag == 'script']
    assert scripts == [{'src': '/setup-assets/login.js', 'defer': None}]
    assert any(tag == 'noscript' for tag, _ in page.tags)


def test_login_form_is_accessible_and_cannot_be_submitted_before_the_account_check():
    page = Page(TestClient(create_app()).get('/login').text)
    fields = page.by_id()
    assert fields['login-form']['novalidate'] is None
    assert fields['login-form']['method'] == 'post'
    assert fields['login-email']['type'] == 'email'
    assert fields['login-email']['autocomplete'] == 'username'
    assert fields['login-password']['type'] == 'password'
    assert fields['login-password']['autocomplete'] == 'current-password'
    for field in ('login-email', 'login-password'):
        assert 'required' in fields[field]
        assert fields[field]['aria-describedby'] == f'{field}-error'
        assert fields[f'{field}-error']['role'] == 'alert'
        assert 'hidden' in fields[f'{field}-error']
    labels = {attrs.get('for') for tag, attrs in page.tags if tag == 'label'}
    assert all(attrs['id'] in labels for tag, attrs in page.tags if tag == 'input')
    submit = fields['login-submit']
    assert submit['type'] == 'submit'
    assert 'disabled' in submit
    assert 'primary' in submit['class'].split()
    for region in ('account-status', 'login-status'):
        assert fields[region]['role'] == 'status'
        assert fields[region]['aria-live'] == 'polite'
    for region in ('account-error', 'login-error'):
        assert fields[region]['role'] == 'alert'
        assert 'hidden' in fields[region]
    assert 'hidden' in fields['signed-in']
    assert fields['continue-link']['href'] == '/setup'


@pytest.mark.parametrize('asset,content_type', [('login.css', 'text/css'), ('login.js', 'javascript')])
def test_login_assets_are_available(asset, content_type):
    response = TestClient(create_app()).get('/setup-assets/' + asset)
    assert response.status_code == 200
    assert content_type in response.headers['content-type']


def test_login_css_only_uses_colours_that_setup_css_already_defines():
    colour = re.compile(r'#[0-9a-fA-F]{3,8}\b')
    setup_colours = set(colour.findall((STATIC / 'setup.css').read_text()))
    login_colours = set(colour.findall((STATIC / 'login.css').read_text()))
    assert login_colours
    assert login_colours <= setup_colours


@pytest.mark.parametrize('scenario', [
    'signed-out', 'signed-in', 'loading', 'me-network', 'me-500', 'me-malformed', 'me-timeout',
    'login', 'login-empty', 'login-401', 'login-403', 'login-422', 'login-500',
    'login-network', 'login-timeout', 'login-csrf-failure', 'login-malformed', 'login-duplicate',
])
def test_login_javascript(scenario):
    run_flow(scenario)


def test_login_requests_are_accepted_by_the_real_authentication_api():
    app = create_app()
    AuthenticatedTestClient(app, email='anna@example.ch')
    calls = run_flow('login')['calls']
    browser = TestClient(app, base_url='https://testserver')
    responses = replay(browser, calls)
    assert [response.status_code for response in responses] == [401, 200, 200]
    assert responses[2].json()['email'] == 'anna@example.ch'
    assert responses[2].json()['csrf_token']
    me = browser.get('/api/v1/auth/me')
    assert me.status_code == 200
    assert me.json()['email'] == 'anna@example.ch'

