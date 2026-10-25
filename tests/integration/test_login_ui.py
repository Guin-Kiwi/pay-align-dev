from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

from src.app.domain.constants import MIN_PASSWORD_LENGTH
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


def run_flow(scenario, email='anna@example.ch', password=TEST_PASSWORD, signup=None, samples=None):
    signup = signup or {
        'first_name': 'Anna', 'last_name': 'Muster', 'email': 'anna@example.ch', 'password': TEST_PASSWORD,
    }
    client = TestClient(create_app())
    page = Page(client.get('/login').text)
    result = subprocess.run(
        [node_binary(), str(FLOW)],
        input=json.dumps({
            'scenario': scenario, 'elements': page.by_id(),
            'javascript': client.get('/setup-assets/login.js').text,
            'credentials': {'email': email, 'password': password},
            'signup': signup, 'samples': samples,
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


def test_sign_up_dialog_shows_the_password_policy_before_the_fields():
    html = TestClient(create_app()).get('/login').text
    page = Page(html)
    fields = page.by_id()
    dialog = next(attrs for tag, attrs in page.tags if tag == 'dialog')
    assert dialog['id'] == 'signup-dialog'
    assert dialog['aria-labelledby'] == 'signup-heading'
    assert 'signup-heading' in fields
    policy = re.search(r'<p id="password-policy">(.*?)</p>', html, re.S).group(1)
    assert f'at least {MIN_PASSWORD_LENGTH} characters' in policy
    assert 'a number' in policy
    assert 'a special character' in policy
    assert 'hidden' not in fields['password-policy']
    assert html.index('id="password-policy"') < html.index('id="signup-first-name"')
    assert 'password-policy' in fields['signup-password']['aria-describedby'].split()
    assert 'signup-password-error' in fields['signup-password']['aria-describedby'].split()


def test_the_page_script_uses_the_configured_minimum_password_length():
    script = (STATIC / 'login.js').read_text()
    assert re.search(r'const MIN_PASSWORD_LENGTH = (\d+);', script).group(1) == str(MIN_PASSWORD_LENGTH)


def test_sign_up_form_is_accessible_and_cannot_be_submitted_before_the_account_check():
    page = Page(TestClient(create_app()).get('/login').text)
    fields = page.by_id()
    assert fields['signup-form']['method'] == 'post'
    assert 'novalidate' in fields['signup-form']
    expected = {
        'signup-first-name': ('text', 'given-name'),
        'signup-last-name': ('text', 'family-name'),
        'signup-email': ('email', 'username'),
        'signup-password': ('password', 'new-password'),
    }
    labels = {attrs.get('for') for tag, attrs in page.tags if tag == 'label'}
    for field, (kind, autocomplete) in expected.items():
        assert fields[field].get('type', 'text') == kind
        assert fields[field]['autocomplete'] == autocomplete
        assert 'required' in fields[field]
        assert field in labels
        assert fields[field]['aria-describedby'].split()[-1] == f'{field}-error'
        assert fields[f'{field}-error']['role'] == 'alert'
        assert 'hidden' in fields[f'{field}-error']
    assert fields['signup-status']['role'] == 'status'
    assert fields['signup-error']['role'] == 'alert'
    assert 'hidden' in fields['signup-error']
    assert fields['signup-submit']['type'] == 'submit'
    assert 'disabled' in fields['signup-submit']
    assert 'disabled' in fields['open-signup']


def test_main_and_secondary_buttons_are_told_apart():
    page = Page(TestClient(create_app()).get('/login').text)
    fields = page.by_id()
    for main in ('login-submit', 'signup-submit'):
        assert fields[main]['class'].split() == ['primary']
    for secondary in ('open-signup', 'signup-cancel'):
        assert fields[secondary]['class'].split() == ['secondary']
        assert fields[secondary]['type'] == 'button'
    css = (STATIC / 'login.css').read_text()
    backgrounds = {}
    for selector in ('.primary:enabled', '.secondary:enabled'):
        rule = re.search(re.escape(selector) + r'\s*\{([^}]*)\}', css)
        assert rule, selector
        backgrounds[selector] = re.search(r'(?<![-\w])background:\s*([^;]+);', rule.group(1)).group(1)
    assert backgrounds['.primary:enabled'] != backgrounds['.secondary:enabled']


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
    'login-invalid-email', 'signup-open', 'signup-cancel', 'signup-empty', 'signup-invalid', 'signup-password-rules',
    'register', 'register-409', 'register-422', 'register-403', 'register-500', 'register-network',
    'register-timeout', 'register-csrf-failure', 'register-malformed', 'register-duplicate',
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



def test_register_requests_are_accepted_by_the_real_authentication_api():
    app = create_app()
    signup = {'first_name': 'Berta', 'last_name': 'Beispiel', 'email': 'berta@example.ch', 'password': TEST_PASSWORD}
    calls = run_flow('register', signup=signup)['calls']
    browser = TestClient(app, base_url='https://testserver')
    responses = replay(browser, calls)
    assert [response.status_code for response in responses] == [401, 200, 201]
    assert responses[2].json()['email'] == 'berta@example.ch'
    assert responses[2].json()['csrf_token']
    me = browser.get('/api/v1/auth/me')
    assert me.status_code == 200
    assert (me.json()['first_name'], me.json()['last_name']) == ('Berta', 'Beispiel')


def test_the_pages_registration_error_handling_matches_the_real_authentication_api():
    app = create_app()
    AuthenticatedTestClient(app, email='anna@example.ch')
    browser = TestClient(app, base_url='https://testserver')
    duplicate = replay(
        TestClient(app, base_url='https://testserver'),
        run_flow('register-409', signup={
            'first_name': 'Anna', 'last_name': 'Muster', 'email': 'anna@example.ch', 'password': TEST_PASSWORD,
        })['calls'],
    )
    assert duplicate[2].status_code == 409
    assert duplicate[2].json() == {'detail': 'An account already uses this email.'}
    token = browser.get('/api/v1/auth/csrf').json()['csrf_token']
    weak = browser.post(
        '/api/v1/auth/register', headers={'X-CSRF-Token': token},
        json={'email': 'berta@example.ch', 'password': 'weakpass', 'first_name': 'Berta', 'last_name': 'Beispiel'},
    )
    assert weak.status_code == 422
    assert isinstance(weak.json()['detail'], str)
    assert str(MIN_PASSWORD_LENGTH) in weak.json()['detail']


def test_login_does_not_apply_the_registration_password_policy():
    run_flow('login', password='x')


PASSWORD_SAMPLES = [
    'Abcdef1!', 'Abcde1!', 'abcdefgh', 'abcdefg1', 'abcdefg!', 'abcdefg 1', 'A-long-test-password-123!',
    'P\u00e4ssw\u00f6rd\u0661!', '\u043f\u0430\u0440\u043e\u043b\u044c12!',
    'abcdefg1\U0001f600', 'a1' + '\U0001f600' * 6, 'a1' + '\U0001f600' * 5, 'abcdefg1\u00b2', 'abcdefg1\u0301',
]
EMAIL_SAMPLES = [
    'anna@example.ch', 'asdasd', 'a@b', 'a@b.c', 'a b@c.de', '@x.y', 'a@@b.c', 'a@b.', '  ben@example.ch  ',
    'c.d+e@sub.example.ch',
]


def test_the_pages_rules_agree_with_the_real_registration_rules():
    rules = run_flow('rules', samples={'passwords': PASSWORD_SAMPLES, 'emails': EMAIL_SAMPLES})['rules']
    browser = TestClient(create_app(), base_url='https://testserver')

    def accepted(email, password):
        token = browser.get('/api/v1/auth/csrf').json()['csrf_token']
        response = browser.post(
            '/api/v1/auth/register', headers={'X-CSRF-Token': token},
            json={'email': email, 'password': password, 'first_name': 'Sample', 'last_name': 'Person'},
        )
        assert response.status_code in (201, 422), (email, password, response.text)
        return response.status_code == 201

    for index, (password, page_accepts) in enumerate(zip(PASSWORD_SAMPLES, rules['passwords'])):
        assert accepted(f'password{index}@example.ch', password) == page_accepts, repr(password)
    for email, page_accepts in zip(EMAIL_SAMPLES, rules['emails']):
        assert accepted(email, TEST_PASSWORD) == page_accepts, repr(email)
