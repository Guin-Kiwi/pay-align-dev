import subprocess
from html.parser import HTMLParser

from src.app.infrastructure.web.app import create_app
from tests.integration.authenticated_client import AuthenticatedTestClient
from tests.integration.page_scripts import STATIC, node_binary


NAVIGATION = (
    ("Home", "/home"),
    ("Timesheets", "/timesheets"),
    ("Employees", "/employees"),
    ("Payslips", "/payslips"),
)
PAGES = ("/home", "/timesheets", "/employees", "/payslips", "/employment-setup", "/account-details")


class NavigationPage(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.nav_depth = 0
        self.buttons = []
        self.nav_found = False
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "nav" and attrs.get("aria-label") == "Main navigation":
            self.nav_depth = 1
            self.nav_found = True
        elif self.nav_depth and tag == "button":
            self.buttons.append({**attrs, "text": ""})
        elif self.nav_depth and tag == "nav":
            self.nav_depth += 1

    def handle_endtag(self, tag):
        if self.nav_depth and tag == "nav":
            self.nav_depth -= 1

    def handle_data(self, data):
        if self.nav_depth and self.buttons:
            self.buttons[-1]["text"] += data.strip()


def test_signed_in_pages_have_consistent_button_navigation():
    app = create_app()
    with AuthenticatedTestClient(app) as client:
        token = client.get("/api/v1/auth/csrf").json()["csrf_token"]
        response = client.post(
            "/api/v1/employer",
            headers={"X-CSRF-Token": token},
            json={
                "name": "Test Employer",
                "address": "Basel",
                "ahv_number": "756.1234.5678.97",
                "contact_info": "test@example.ch",
            },
        )
        assert response.status_code == 201

        for route in PAGES:
            page_response = client.get(route)
            assert page_response.status_code == 200
            assert page_response.text.index('class="app-header') < page_response.text.index("<main")
            assert page_response.text.count('aria-label="Main navigation"') == 1
            page = NavigationPage(page_response.text)
            assert page.nav_found, route
            assert f'data-current-route="{route}"' in page_response.text
            assert [(button["text"], button["data-route"]) for button in page.buttons[:-1]] == list(NAVIGATION)
            assert (page.buttons[-1].get("id"), page.buttons[-1]["text"]) == ("logout-button", "Log out")
            assert "/setup-assets/navigation.js" in page_response.text


def test_navigation_script_is_available():
    response = AuthenticatedTestClient(create_app()).get(
        "/setup-assets/navigation.js"
    )
    assert response.status_code == 200
    assert "data-route" in response.text


def test_shared_navigation_header_stays_at_the_top_without_covering_page_content():
    with AuthenticatedTestClient(create_app()) as client:
        page = client.get("/home").text
        assert "<!-- SHARED_NAVIGATION -->" not in page
        stylesheet = client.get("/setup-assets/base.css").text
        assert "position: sticky" in stylesheet
        assert "width: min(90rem, calc(100% - 2rem))" in stylesheet
        assert "border: 1px solid #dbe4e5" in stylesheet
        assert "border-radius: .6rem" in stylesheet


def signed_in_client_with_employer():
    client = AuthenticatedTestClient(create_app())
    token = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    employer = {"name": "Test Employer", "address": "Basel", "ahv_number": "756.1234.5678.97", "contact_info": "test@example.ch"}
    assert client.post("/api/v1/employer", headers={"X-CSRF-Token": token}, json=employer).status_code == 201
    return client


def test_every_page_but_home_has_a_back_button_in_the_header():
    with signed_in_client_with_employer() as client:
        for route in PAGES:
            html = client.get(route).text
            if route == "/home":
                assert 'id="back-button"' not in html, route
                continue
            header = html[html.index('<header class="app-header'):html.index("</header>")]
            assert '<button id="back-button" class="back-button" type="button">Back</button>' in header, route
            assert header.index('id="back-button"') < header.index("<nav"), route
            assert header.index('id="back-button"') < header.index('class="brand"'), route
            assert "{{" not in html, route
        assert "data-home" in client.get("/timesheets").text


def test_back_button_goes_back_or_home_when_there_is_no_history():
    result = subprocess.run(
        [node_binary(), str(STATIC.parents[3] / "tests" / "fixtures" / "navigation_back.js"), str(STATIC / "navigation.js")],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == "ok"


def test_back_button_is_styled_like_the_other_header_buttons():
    css = AuthenticatedTestClient(create_app()).get("/setup-assets/base.css").text
    assert ".back-button" in css
    assert '.back-button::before { content: "\\2190 "' in css
