import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from src.app.infrastructure.web.app import create_app
from tests.integration.page_scripts import STATIC

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "common_helpers.js"


def test_common_script_is_served_with_the_shared_helpers():
    response = TestClient(create_app()).get("/setup-assets/common.js")
    assert response.status_code == 200
    for declaration in ("const element", "async function call", "async function fetchCsrfToken", "function wireWarningDialog"):
        assert declaration in response.text


def test_common_helpers_build_requests_and_read_the_csrf_token():
    subprocess.run(["node", str(FIXTURE), str(STATIC / "common.js")], check=True, timeout=10)


def test_static_assets_are_revalidated_on_every_load_so_changes_always_show():
    client = TestClient(create_app())
    for asset in ("common.js", "timesheets.js", "employments.css", "setup.css"):
        first = client.get(f"/setup-assets/{asset}")
        assert first.status_code == 200, asset
        assert first.headers["cache-control"] == "no-cache", asset
        again = client.get(f"/setup-assets/{asset}", headers={"If-None-Match": first.headers["etag"]})
        assert again.status_code == 304, asset
        assert again.headers["cache-control"] == "no-cache", asset
