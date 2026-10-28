import json
from pathlib import Path
import re
import subprocess

import pytest
from fastapi.testclient import TestClient

from src.app.domain.constants import MIN_PASSWORD_LENGTH
from src.app.infrastructure.web.app import create_app
from tests.integration.page_scripts import Page, node_binary, page_javascript
from tests.integration.authenticated_client import TEST_PASSWORD, AuthenticatedTestClient

STATIC = Path(__file__).resolve().parents[2] / 'src' / 'app' / 'interfaces' / 'static'
FLOW = Path(__file__).resolve().parents[1] / 'fixtures' / 'login_flow.js'




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
            'javascript': page_javascript(client, 'login', rules=True),
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
    assert [href.split('?')[0] for href in stylesheets] == ['/setup-assets/base.css', '/setup-assets/login.css']
    scripts = [attrs for tag, attrs in page.tags if tag == 'script']
    assert scripts == [{'src': '/setup-assets/constants.js', 'defer': None}, {'src': '/setup-assets/common.js', 'defer': None}, {'src': '/setup-assets/login.js', 'defer': None}]
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
        assert 'hidden' not in fields[f'{field}-error']
        assert 'field-error' in fields[f'{field}-error']['class'].split()
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
    assert 'signed-in' not in fields and 'continue-link' not in fields


@pytest.mark.parametrize('asset,content_type', [('login.css', 'text/css'), ('login.js', 'javascript')])
def test_login_assets_are_available(asset, content_type):
    response = TestClient(create_app()).get('/setup-assets/' + asset)
    assert response.status_code == 200
    assert content_type in response.headers['content-type']


def test_sign_up_dialog_always_lists_the_password_requirements_under_the_password_field():
    html = TestClient(create_app()).get('/login').text
    page = Page(html)
    fields = page.by_id()
    dialog = next(attrs for tag, attrs in page.tags if tag == 'dialog')
    assert dialog['id'] == 'signup-dialog'
    assert dialog['aria-labelledby'] == 'signup-heading'
    assert 'signup-heading' in fields
    assert 'id="password-policy"' not in html
    listed = re.search(r'<div id="password-requirements"[^>]*>(.*?)</div>', html, re.S).group(1)
    assert re.findall(r'<li id="requirement-\w+" data-met="false">(.*?)</li>', listed, re.S) == [
        f'at least {MIN_PASSWORD_LENGTH} characters',
        'a number',
        'a special character (not a letter, number or space)',
    ]
    for name in ('length', 'number', 'special'):
        assert fields[f'requirement-{name}']['data-met'] == 'false'
    assert 'hidden' not in fields['password-requirements']
    assert 'requirements' in fields['password-requirements']['class'].split()
    assert html.index('id="signup-password"') < html.index('id="password-requirements"') < html.index('id="signup-password-error"')
    assert fields['signup-password']['aria-describedby'].split() == ['password-requirements', 'signup-password-error']


def test_the_page_script_takes_the_minimum_password_length_from_the_rules_script():
    script = (STATIC / 'login.js').read_text()
    assert 'MIN_PASSWORD_LENGTH' in script
    assert not re.search(r'const MIN_PASSWORD_LENGTH\b', script)


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
        assert 'hidden' not in fields[f'{field}-error']
        assert 'field-error' in fields[f'{field}-error']['class'].split()
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


def css_rule(css, selector):
    match = re.search(re.escape(selector) + r'\s*\{([^}]*)\}', css)
    assert match, selector
    return dict(
        (name.strip(), value.strip())
        for name, value in (declaration.split(':', 1) for declaration in match.group(1).split(';') if declaration.strip())
    )


def test_field_notes_reserve_their_space_and_the_flagged_field_turns_red_without_moving():
    page = Page(TestClient(create_app()).get('/login').text)
    notes = [
        attrs for _, attrs in page.tags
        if re.fullmatch(r'(login|signup)-(email|password|first-name|last-name)-error', attrs.get('id', ''))
    ]
    assert len(notes) == 6
    for attrs in notes:
        assert attrs['role'] == 'alert'
        assert 'hidden' not in attrs
        assert 'field-error' in attrs['class'].split()
    css = (STATIC / 'login.css').read_text()
    note = css_rule(css, '.field-error')
    assert note['line-height'] == '1.4'
    assert float(note['min-height'].removesuffix('em')) >= 1.4
    assert not {'display', 'visibility', 'height'} & set(note)
    assert float(css_rule(css, '#signup-email-error')['min-height'].removesuffix('em')) >= 2.8
    flagged = css_rule(css, 'input[aria-invalid="true"]')
    assert flagged['border-color'] == '#912323'
    assert not {'border', 'border-width', 'padding', 'margin', 'width', 'height'} & set(flagged)


def test_met_requirements_turn_green_and_unmet_ones_red_once_flagged_without_resizing():
    css = (STATIC / 'login.css').read_text()
    met = css_rule(css, '.requirements li[data-met="true"]')
    assert met['color'] == '#116257'
    assert set(met) == {'color'}
    flagged = css_rule(css, '#signup-password[aria-invalid="true"] + .requirements li[data-met="false"]')
    assert flagged['color'] == '#912323'
    assert set(flagged) == {'color'}
    marker = css_rule(css, '.requirements li::before')
    assert marker['display'] == 'inline-block'
    assert 'width' in marker
    assert 'content' in css_rule(css, '.requirements li[data-met="false"]::before')
    done = css_rule(css, '.requirements li[data-met="true"]::before')
    assert set(done) == {'content'}
    assert any(tick in done['content'] for tick in ('\u2713', '\\2713'))
    assert css_rule(css, '.requirements li')['list-style'] == 'none'


def test_sign_up_dialog_is_wide_and_compact_so_that_it_fits_a_laptop_screen():
    html = TestClient(create_app()).get('/login').text
    assert (
        html.index('class="name-row"') < html.index('id="signup-first-name"')
        < html.index('id="signup-first-name-error"') < html.index('for="signup-last-name"')
        < html.index('id="signup-last-name-error"') < html.index('for="signup-email"')
    )
    assert html.count('<div class="field">') == 2
    css = (STATIC / 'login.css').read_text()
    assert float(re.match(r'min\(([\d.]+)rem', css_rule(css, 'dialog')['width']).group(1)) >= 40
    wide = re.search(r'@media \(min-width: 36rem\)\s*\{(.*?)\n\}', css, re.S).group(1)
    assert css_rule(wide, '.name-row')['grid-template-columns'] == '1fr 1fr'
    assert float(css_rule(wide, '#signup-email-error')['min-height'].removesuffix('em')) == 1.4
    assert css_rule(css, '.name-row')['display'] == 'grid'
    assert css_rule(css, '.requirements ul')['display'] == 'flex'
    assert css_rule(css, '.requirements ul')['flex-wrap'] == 'wrap'
    assert re.search(r'<div class="actions">(?:(?!</div>).)*id="signup-status"', html, re.S)


def test_login_css_only_uses_colours_that_setup_css_already_defines():
    colour = re.compile(r'#[0-9a-fA-F]{3,8}\b')
    setup_colours = set(colour.findall((STATIC / 'base.css').read_text()))
    login_colours = set(colour.findall((STATIC / 'login.css').read_text()))
    assert login_colours
    assert login_colours <= setup_colours


@pytest.mark.parametrize('scenario', [
    'signed-out', 'signed-in', 'loading', 'me-network', 'me-500', 'me-malformed', 'me-timeout',
    'login', 'login-empty', 'login-401', 'login-403', 'login-422', 'login-500',
    'login-network', 'login-timeout', 'login-csrf-failure', 'login-malformed', 'login-duplicate', 'login-again-401',
    'link-signup', 'link-signed-in', 'link-signed-in-with-employer', 'link-me-500',
    'signed-in-with-employer', 'signed-in-lookup-error', 'signed-in-lookup-network',
    'signed-in-lookup-malformed', 'signed-in-lookup-other-404', 'login-with-employer', 'login-lookup-error',
    'login-invalid-email', 'blur-validation', 'signup-open', 'signup-cancel', 'signup-empty', 'signup-invalid', 'signup-password-rules',
    'register', 'register-lookup-error', 'register-409', 'register-422', 'register-403', 'register-500', 'register-network',
    'register-timeout', 'register-csrf-failure', 'register-malformed', 'register-duplicate',
    'register-again-409',
])
def test_login_javascript(scenario):
    run_flow(scenario)


def test_login_requests_are_accepted_by_the_real_authentication_api():
    app = create_app()
    AuthenticatedTestClient(app, email='anna@example.ch')
    calls = run_flow('login')['calls']
    browser = TestClient(app, base_url='https://testserver')
    responses = replay(browser, calls)
    assert [response.status_code for response in responses] == [401, 200, 200, 404]
    assert responses[3].json() == {'detail': 'No employer is set up yet.'}
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
    assert [response.status_code for response in responses] == [401, 200, 201, 404]
    assert responses[3].json() == {'detail': 'No employer is set up yet.'}
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


SETUP = {
    'employer': {'name': 'Anna Muster', 'address': 'Basel', 'ahv_number': '756.1234.5678.97', 'contact_info': 'anna@example.ch'},
    'employee': {'name': 'Maria Muster', 'address': 'Basel', 'ahv_number': '756.9876.5432.10', 'nationality': 'CH'},
    'employment': {'start_date': '2026-01-01', 'hourly_wage': '28.50', 'weekly_hours': '6:00'},
}


def test_the_pages_employer_check_matches_the_real_api_for_an_account_with_an_employer():
    app = create_app()
    owner = AuthenticatedTestClient(app, email='anna@example.ch')
    assert owner.post('/api/v1/setup', json=SETUP).status_code == 201
    calls = run_flow('login-with-employer')['calls']
    responses = replay(TestClient(app, base_url='https://testserver'), calls)
    assert [response.status_code for response in responses] == [401, 200, 200, 200]
    employer = responses[3].json()
    assert isinstance(employer['id'], int) and employer['id'] > 0
    assert employer['name'] == 'Anna Muster'
    assert run_flow('login-with-employer')['assigned'] == ['/home']


def test_an_employer_that_belongs_to_another_account_does_not_count_for_the_page():
    app = create_app()
    owner = AuthenticatedTestClient(app, email='anna@example.ch')
    assert owner.post('/api/v1/setup', json=SETUP).status_code == 201
    AuthenticatedTestClient(app, email='bea@example.ch')
    calls = run_flow('login', email='bea@example.ch')['calls']
    responses = replay(TestClient(app, base_url='https://testserver'), calls)
    assert [response.status_code for response in responses] == [401, 200, 200, 404]
    assert responses[3].json() == {'detail': 'No employer is set up yet.'}
    assert owner.get('/api/v1/employer').status_code == 200
