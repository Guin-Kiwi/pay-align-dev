from html.parser import HTMLParser

import pytest
from fastapi.testclient import TestClient

from src.app.infrastructure.web.app import create_app


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.tags = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def test_setup_page_is_accessible_and_cannot_submit():
    client = TestClient(create_app())
    response = client.get('/setup')
    assert response.status_code == 200
    assert response.headers['content-type'].startswith('text/html')
    page = Page(response.text)
    assert ('html', {'lang': 'de'}) in page.tags
    for text in ('Beschäftigung einrichten', 'Arbeitgeber', 'Arbeitnehmer', 'Beschäftigung', 'API-Vertrag'):
        assert text in response.text
    button = next(attrs for tag, attrs in page.tags if tag == 'button' and attrs.get('id') == 'save-setup')
    assert 'disabled' in button
    assert button['type'] == 'button'
    for field in ('weekly-hours', 'holiday-entitlement'):
        attrs = next(attrs for tag, attrs in page.tags if attrs.get('id') == field)
        assert 'disabled' in attrs
        assert attrs['aria-describedby'] == 'contract-note'
    inputs = [attrs for tag, attrs in page.tags if tag == 'input']
    labels = {attrs.get('for') for tag, attrs in page.tags if tag == 'label'}
    assert all(attrs['id'] in labels for attrs in inputs)
    assert any(attrs.get('role') == 'status' for _, attrs in page.tags)
    assert any(attrs.get('role') == 'alert' for _, attrs in page.tags)


@pytest.mark.parametrize('asset,content_type', [('setup.css', 'text/css'), ('setup.js', 'javascript')])
def test_setup_assets_are_available(asset, content_type):
    response = TestClient(create_app()).get('/setup-assets/' + asset)
    assert response.status_code == 200
    assert content_type in response.headers['content-type']


def test_employer_lookup_uses_existing_api_without_configuring_an_employer():
    client = TestClient(create_app())
    assert client.get('/setup').status_code == 200
    assert client.get('/api/v1/employer').status_code == 404


def test_existing_employer_remains_available_after_loading_page():
    client = TestClient(create_app())
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
        'employment': {'start_date': '2026-01-01', 'hourly_wage': '28.50', 'weekly_hours': 6},
    })
    assert response.status_code == 201
    assert client.get('/setup').status_code == 200
    assert client.get('/api/v1/employer').json() == {'id': 1, **employer}
    assert TestClient(create_app()).get('/api/v1/employer').status_code == 404
