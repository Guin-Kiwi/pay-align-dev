from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.app.domain.constants import RULES_YEAR
from src.app.infrastructure.web.app import create_app
from tests.integration.authenticated_client import AuthenticatedTestClient
from tests.integration.page_scripts import Page, node_binary, page_javascript


EMPLOYMENT_SETUP_SUBMISSION_FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures' / 'employment_setup_submission.js'


def create_employer(client):
    token = client.get('/api/v1/auth/csrf').json()['csrf_token']
    details = {'name': 'Anna', 'address': 'Basel', 'ahv_number': '756.1234.5678.97', 'contact_info': 'anna@example.ch'}
    assert client.post('/api/v1/employer', json=details, headers={'X-CSRF-Token': token}).status_code == 201


def test_add_employment_warns_before_saving_because_it_cannot_be_changed():
    client = AuthenticatedTestClient(create_app())
    create_employer(client)
    html = client.get('/employment-setup').text
    assert '<dialog id="add-employment-dialog" class="warning" aria-labelledby="add-employment-dialog-heading">' in html
    assert '<h2 id="add-employment-dialog-heading">Are you sure?</h2>' in html
    assert 'cannot be changed' in html
    assert 'saved details are kept' in html
    for label in ('Yes, add this employment', 'No, go back'):
        assert f'>{label}</button>' in html
    assert 'dialog.warning::backdrop' in client.get('/setup-assets/base.css').text


def test_unauthenticated_employment_setup_page_redirects_to_login():
    response = TestClient(create_app()).get('/employment-setup', follow_redirects=False)
    assert response.status_code == 303
    assert response.headers['location'] == '/login'


def test_employment_setup_is_gated_until_the_employer_profile_exists():
    client = AuthenticatedTestClient(create_app())
    response = client.get('/employment-setup', follow_redirects=False)
    assert response.status_code == 303
    assert response.headers['location'] == '/home'


def test_employment_setup_page_is_accessible_and_initially_cannot_submit():
    client = AuthenticatedTestClient(create_app())
    create_employer(client)
    response = client.get('/employment-setup')
    assert response.status_code == 200
    assert response.headers['content-type'].startswith('text/html')
    assert 'configured database' not in response.text
    assert 'lost after a server restart' not in response.text
    page = Page(response.text)
    assert ('html', {'lang': 'en'}) in page.tags
    for text in ('Set up employment', 'Your details', 'Employee', 'Employment'):
        assert text in response.text
    assert 'Employee tax status defaults to ordinary taxation.' not in response.text
    assert (
        'Minimum CHF 22.20 per hour, with at most two decimal places. This is the legal '
        'minimum only below 5 hours a week. From 5 hours a week, the NAV Hauswirtschaft '
        'minimum applies instead: CHF 20.35 (unskilled), 22.30 (4 years\' experience or an '
        'EBA certificate) or 24.55 (an EFZ certificate). PayAlign does not check which '
        'category applies, so it accepts only CHF 22.20 or more.'
    ) in response.text
    button = next(attrs for tag, attrs in page.tags if tag == 'button' and attrs.get('id') == 'save-setup')
    assert 'disabled' in button
    assert button['type'] == 'submit'
    fields = {attrs['id']: attrs for _, attrs in page.tags if 'id' in attrs}
    assert 'disabled' not in fields['weekly-hours']
    assert fields['weekly-hours']['type'] == 'text'
    assert fields['weekly-hours']['placeholder'] == '6:30'
    assert 'disabled' not in fields['holiday-weeks']
    assert fields['start-date']['min'] == '2026-01-01'
    assert fields['start-date']['max'] == '2026-12-31'
    assert 'required' in fields['start-date']
    assert fields['end-date']['type'] == 'date'
    assert 'required' not in fields['end-date']
    assert 'max' not in fields['end-date']
    assert fields['hourly-wage']['min'] == '22.20'
    assert fields['hourly-wage']['max'] == '500.00'
    assert fields['hourly-wage']['step'] == '0.01'
    assert fields['employer-name']['autocomplete'] == 'section-employer name'
    assert fields['employer-address']['autocomplete'] == 'section-employer street-address'
    assert fields['employee-name']['autocomplete'] == 'section-employee name'
    assert fields['employee-address']['autocomplete'] == 'section-employee street-address'
    options = [attrs for tag, attrs in page.tags if tag == 'option']
    assert options == [{'value': '4', 'selected': None}, {'value': '5'}]
    assert 'holiday-entitlement' not in fields
    inputs = [attrs for tag, attrs in page.tags if tag == 'input']
    labels = {attrs.get('for') for tag, attrs in page.tags if tag == 'label'}
    assert all(attrs['id'] in labels for attrs in inputs)
    assert any(attrs.get('role') == 'status' for _, attrs in page.tags)
    assert any(attrs.get('role') == 'alert' for _, attrs in page.tags)
    assert fields['setup-complete-actions']['hidden'] is None
    assert fields['view-employments']['type'] == 'button'


@pytest.mark.parametrize('asset,content_type', [('base.css', 'text/css'), ('employment-setup.js', 'javascript')])
def test_employment_setup_assets_are_available(asset, content_type):
    response = TestClient(create_app()).get('/setup-assets/' + asset)
    assert response.status_code == 200
    assert content_type in response.headers['content-type']
    if asset == 'employment-setup.js':
        assert 'lost after a server restart' not in response.text


def test_employer_lookup_uses_existing_api_without_configuring_an_employer():
    client = AuthenticatedTestClient(create_app())
    assert client.get('/employment-setup', follow_redirects=False).status_code == 303
    assert client.get('/api/v1/employer').status_code == 404


def test_existing_employer_remains_available_after_loading_page():
    client = AuthenticatedTestClient(create_app())
    employer = {
        'name': 'Anna Muster',
        'address': 'Basel',
        'ahv_number': '756.1234.5678.97',
        'contact_info': 'anna@example.ch',
    }
    response = client.post('/api/v1/setup', json={
        'employer': employer,
        'employee': {
            'name': 'Maria Muster', 'address': 'Basel',
            'ahv_number': '756.9876.5432.10', 'nationality': 'CH',
        },
        'employment': {'start_date': '2026-01-01', 'hourly_wage': '28.50', 'weekly_hours': '6:00'},
    })
    assert response.status_code == 201
    assert client.get('/employment-setup').status_code == 200
    assert client.get('/api/v1/employer').json() == {'id': 1, **employer}
    assert TestClient(create_app()).get('/api/v1/employer').status_code == 401


@pytest.mark.parametrize('employer_name', ['Anna Muster', '<img src=x onerror=alert(1)>'])
def test_existing_employer_javascript_displays_details_safely(employer_name):
    import json
    import subprocess

    node = node_binary()

    client = AuthenticatedTestClient(create_app())
    create_employer(client)
    page = Page(client.get('/employment-setup').text)
    initial_elements = {attrs['id']: attrs for _, attrs in page.tags if 'id' in attrs}
    employer = {
        'id': 1,
        'name': employer_name,
        'address': 'Freie Strasse 1, Basel',
        'ahv_number': '756.1234.5678.97',
        'contact_info': 'anna@example.ch',
    }
    javascript = page_javascript(client, 'employment-setup', rules=True)
    harness = r'''
const assert = require('node:assert/strict');
const vm = require('node:vm');
let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => input += chunk);
process.stdin.on('end', async () => {
  try {
    const {elements: attributes, employer, javascript} = JSON.parse(input);
    function element(attrs = {}) {
      return {
        hidden: Object.hasOwn(attrs, 'hidden'),
        disabled: Object.hasOwn(attrs, 'disabled'),
        textContent: '',
        children: [],
        id: attrs.id,
        value: attrs.value ?? '',
        listeners: {},
        setCustomValidity(message) { this.validationMessage = message; },
        setAttribute(name, value) { this[name] = value; },
        addEventListener(event, callback) { this.listeners[event] = callback; },
        append(...children) { this.children.push(...children); },
        set innerHTML(value) { throw new Error('Employer data must be rendered as text'); }
      };
    }
    const elements = Object.fromEntries(Object.entries(attributes).map(([id, attrs]) => [id, element(attrs)]));
    const calls = [];
    await vm.runInNewContext(javascript, {
      document: {
        getElementById(id) { assert.ok(elements[id], id); return elements[id]; },
        createElement(tag) { assert.ok(['dt', 'dd'].includes(tag)); return element(); }
      },
      fetch: async (url, options = {}) => {
        calls.push({url, options});
        if (url === '/api/v1/auth/csrf') return {status: 200, ok: true, json: async () => ({csrf_token: 'test-csrf-token'})};
        return {status: 200, ok: true, json: async () => employer};
      },
      AbortController, setTimeout, clearTimeout
    }, {timeout: 1000});
    assert.equal(calls.length, 2);
    assert.equal(calls[0].url, '/api/v1/auth/csrf');
    assert.equal(calls[1].url, '/api/v1/employer');
    assert.equal(calls[1].options.method ?? 'GET', 'GET');
    assert.equal(elements['employer-status'].textContent, '');
    assert.equal(elements['employer-details'].hidden, false);
    assert.deepEqual(elements['employer-details'].children.map(child => child.textContent), [
      'Name', employer.name, 'Address', employer.address,
      'AHV number', employer.ahv_number, 'Contact details', employer.contact_info
    ]);
    assert.equal(elements['employer-fields'].hidden, true);
    assert.equal(elements['employer-fields'].disabled, true);
    assert.equal(elements['employer-error'].hidden, true);
    assert.equal(elements['save-setup'].disabled, false);
    for (const id of ['weekly-hours', 'holiday-weeks', 'end-date']) {
      assert.equal(elements[id].disabled, false, id);
    }
    function check(id, value, valid, event = 'input') {
      const field = elements[id];
      field.value = value;
      field.listeners[event]();
      assert.equal(field.validationMessage === '', valid, `${id}: ${value}`);
      assert.equal(field['aria-invalid'], String(!valid));
    }
    for (const value of ['0:01', '00:01', '6:30', '30:15', '99:59']) check('weekly-hours', value, true);
    for (const value of ['', '0:00', '00:00', '6.5', '6:5', '6:60', '100:00', '٦:٣٠', ' 6:30', '6:30\n']) {
      check('weekly-hours', value, false);
    }
    for (const value of ['22.20', '28.5', '28.50', '100', '500', '500.00']) check('hourly-wage', value, true);
    for (const value of ['', '22.19', '28.505', '500.01', '501', '-1', 'NaN']) check('hourly-wage', value, false);
    for (const value of ['2026-01-01', '2026-12-31']) check('start-date', value, true);
    for (const value of ['', '2025-12-31', '2027-01-01', '2026-02-30']) check('start-date', value, false);
    check('start-date', '2026-03-01', true);
    for (const value of ['', '2026-03-01', '2027-08-31']) check('end-date', value, true);
    check('end-date', '2026-02-28', false);
    check('end-date', '2026-03-02', true);
    check('start-date', '2026-03-03', true);
    assert.notEqual(elements['end-date'].validationMessage, '');
    for (const value of ['4', '5']) check('holiday-weeks', value, true, 'change');
    check('holiday-weeks', '20', false, 'change');
    assert.equal(calls.length, 2, 'Editing must not submit or fetch');
    assert.equal(elements['save-setup'].disabled, false);
    console.log('Existing employer UI state verified');
  } catch (error) {
    console.error(error);
    process.exitCode = 1;
  }
});
'''
    result = subprocess.run(
        [node, '-e', harness],
        input=json.dumps({'elements': initial_elements, 'employer': employer, 'javascript': javascript}),
        text=True, capture_output=True, timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'Existing employer UI state verified' in result.stdout
    assert client.get('/api/v1/employer').status_code == 200


@pytest.mark.parametrize('scenario', [
    'new', 'existing', 'end-date', 'duplicate', 'loading', 'invalid',
    'required-empty',
    'lookup-network', 'lookup-401', 'lookup-500', 'lookup-malformed', 'lookup-id', 'lookup-404',
    '400', '401', '403', '409', '422', '500', 'network', 'malformed-success', 'invalid-json',
    'refresh-failure', 'timeout', '200', 'holiday-five', 'cancel',
])
def test_employment_setup_submission_javascript(scenario, monkeypatch, tmp_path):
    import json
    import subprocess

    node = node_binary()
    client = AuthenticatedTestClient(create_app())
    create_employer(client)
    html = client.get('/employment-setup').text
    elements = {attrs['id']: attrs for _, attrs in Page(html).tags if 'id' in attrs}
    if scenario == 'new':
        monkeypatch.chdir(tmp_path)
    result = subprocess.run(
        [node, str(EMPLOYMENT_SETUP_SUBMISSION_FIXTURE)],
        input=json.dumps({'scenario': scenario, 'year': RULES_YEAR, 'elements': elements,
                          'javascript': page_javascript(client, 'employment-setup', rules=True)}),
        text=True, capture_output=True, timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    posts = json.loads(result.stdout)
    if scenario in ('new', 'existing', 'end-date', 'duplicate', 'refresh-failure', 'holiday-five'):
        response = client.post('/api/v1/setup', json=posts[0])
        assert response.status_code == 201
        assert client.get('/api/v1/employer').status_code == 200


def test_ui_setup_payload_persists_across_app_restarts(monkeypatch, tmp_path):
    import json
    from datetime import date
    import subprocess

    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from src.app.infrastructure.orm_models import EmployeeRow, EmploymentRow

    node = node_binary()

    database = tmp_path / 'setup.db'
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{database}')
    with AuthenticatedTestClient(create_app()) as client:
        assert client.get('/api/v1/employer').status_code == 404
        employer = {'name': 'Anna', 'address': 'Basel', 'ahv_number': '756.1234.5678.97', 'contact_info': 'anna@example.ch'}
        token = client.get('/api/v1/auth/csrf').json()['csrf_token']
        assert client.post('/api/v1/employer', json=employer, headers={'X-CSRF-Token': token}).status_code == 201
        html = client.get('/employment-setup').text
        elements = {attrs['id']: attrs for _, attrs in Page(html).tags if 'id' in attrs}
        result = subprocess.run(
            [node, str(EMPLOYMENT_SETUP_SUBMISSION_FIXTURE)],
            input=json.dumps({'scenario': 'holiday-five', 'year': RULES_YEAR, 'elements': elements,
                              'javascript': page_javascript(client, 'employment-setup', rules=True)}),
            text=True, capture_output=True, timeout=10,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        posts = json.loads(result.stdout)
        assert len(posts) == 1
        payload = posts[0]
        response = client.post('/api/v1/setup', json=payload)
        assert response.status_code == 201
        saved = response.json()

    assert database.is_file()
    restarted = create_app()
    with AuthenticatedTestClient(restarted, register=False) as client:
        response = client.get('/api/v1/employer')
        assert response.status_code == 200
        assert response.json() == {'id': saved['employer_id'], **employer}
        with Session(restarted.state.engine) as session:
            employee = session.scalars(select(EmployeeRow)).one()
            assert employee.id == saved['employee_id']
            assert {field: getattr(employee, field) for field in payload['employee']} == payload['employee']
            employment = session.scalars(select(EmploymentRow)).one()
            assert employment.id == saved['employment_id']
            assert employment.employer_id == saved['employer_id']
            assert employment.employee_id == employee.id
            assert employment.start_date == date.fromisoformat(payload['employment']['start_date'])
            assert employment.end_date is None
            assert employment.hourly_wage_cents == 2850
            assert employment.weekly_minutes == 390
            assert employment.holiday_weeks == 5
