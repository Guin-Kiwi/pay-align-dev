import json
import subprocess
from pathlib import Path

import pytest

from src.app.infrastructure.web.app import create_app
from tests.integration.authenticated_client import AuthenticatedTestClient
from tests.integration.page_scripts import Page, node_binary

FLOW = Path(__file__).resolve().parents[1] / "fixtures" / "workspace_flow.js"


@pytest.mark.parametrize("scenario", [
    "holidays-401", "empty", "list-401", "list", "completed-month", "months-401",
    "fill-month", "fill-boundaries", "public-holiday", "annual-holiday", "split-shift",
    "regenerate-warning", "leave-warning", "submit-month", "duplicate-submit", "payroll-401", "payroll-403", "payroll-network",
])
def test_home_employment_workspace(scenario):
    client = AuthenticatedTestClient(create_app())
    page = Page(client.get("/employments").text)
    fields = {key.removeprefix("workspace-"): value for key, value in page.by_id().items() if key.startswith("workspace-")}
    assert not {"payslip-section", "payslip-details", "payslip-month"} & set(fields)
    javascript = "\n".join(client.get(f"/setup-assets/{name}.js").text for name in ("constants", "common", "workspace"))
    result = subprocess.run(
        [node_binary(), str(FLOW)],
        input=json.dumps({"scenario": scenario, "elements": fields, "javascript": javascript}),
        text=True, capture_output=True, timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr
