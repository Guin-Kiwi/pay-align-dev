"""Run explicitly with TEST_DOCKER_IMAGE pointing to a locally built image."""

import os
import secrets
import shutil
import subprocess
import time
from contextlib import contextmanager
from uuid import uuid4

import httpx
import pytest

from tests.e2e.test_demo_flow import SETUP
from tests.integration.authenticated_client import TEST_PASSWORD

IMAGE = os.environ.get("TEST_DOCKER_IMAGE")
pytestmark = pytest.mark.skipif(not IMAGE, reason="Set TEST_DOCKER_IMAGE to test a built image")

ACCOUNT = {
    "email": "container-test@example.ch",
    "password": TEST_PASSWORD,
    "first_name": "Test",
    "last_name": "Employer",
}


def docker(*args):
    return subprocess.check_output(["docker", *args], text=True).strip()


def test_image_defaults_to_nonroot_with_writable_data_directory():
    docker(
        "run", "--rm", "--entrypoint", "python", IMAGE, "-c",
        "import os, pathlib, sys; "
        "assert os.getuid() != 0, 'Container runs as root'; "
        "assert os.getgid() != 0, 'Container uses the root group'; "
        "assert sys.version_info[:2] == (3, 12); "
        "pathlib.Path('/app/data/permission-check').write_text('ok')",
    )


def test_image_contains_only_declared_runtime_files():
    docker(
        "run", "--rm", "--entrypoint", "python", IMAGE, "-c",
        "from pathlib import Path; "
        "root = Path('/app'); "
        "assert {p.name for p in root.iterdir()} == "
        "{'src', 'requirements.txt', 'LICENSE', 'data'}, 'Unexpected image contents'; "
        "assert (root / 'src/app/infrastructure/web/app.py').is_file(); "
        "assert (root / 'requirements.txt').is_file(); "
        "assert (root / 'LICENSE').is_file(); "
        "assert (root / 'data').is_dir() and not any((root / 'data').iterdir())",
    )


def test_image_excludes_test_dependencies():
    docker(
        "run", "--rm", "--entrypoint", "python", IMAGE, "-c",
        "import importlib.util; "
        "assert importlib.util.find_spec('pytest') is None, 'pytest is in the runtime image'; "
        "assert importlib.util.find_spec('httpx') is None, 'httpx is in the runtime image'",
    )


@contextmanager
def running_container(storage):
    name = f"payalign-nonroot-test-{uuid4().hex}"
    try:
        docker(
            "run", "--detach", "--name", name,
            "--mount", f"type=bind,source={storage},target=/app/data",
            "--env", "DATABASE_URL=sqlite:////app/data/payroll.db",
            "--env", f"SESSION_SECRET_KEY={secrets.token_urlsafe(32)}",
            "--env", "SESSION_COOKIE_SECURE=false",
            "--publish", "127.0.0.1::8000", IMAGE,
        )
        address = docker("port", name, "8000/tcp")
        with httpx.Client(base_url=f"http://{address}", timeout=2) as client:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                try:
                    response = client.get("/health")
                    if response.status_code == 200 and response.json() == {"status": "ok"}:
                        break
                except httpx.TransportError:
                    pass
                time.sleep(0.1)
            else:
                pytest.fail("Container did not become healthy")
            yield client, name
    except BaseException:
        subprocess.run(["docker", "logs", name], check=False)
        raise
    finally:
        docker("rm", "--force", name)


def setup_snapshot(name):
    return docker(
        "exec", name, "python", "-c",
        "import json, sqlite3; "
        "db = sqlite3.connect('/app/data/payroll.db'); "
        "rows = {table: db.execute(f'SELECT * FROM {table} ORDER BY id').fetchall() "
        "for table in ('accounts', 'employers', 'employees', 'employments')}; "
        "assert all(len(records) == 1 for records in rows.values()); "
        "print(json.dumps(rows, sort_keys=True))",
    )


def authenticate(client, *, register):
    csrf = client.get("/api/v1/auth/csrf")
    assert csrf.status_code == 200, csrf.text
    credentials = ACCOUNT if register else {
        "email": ACCOUNT["email"], "password": ACCOUNT["password"],
    }
    response = client.post(
        f"/api/v1/auth/{'register' if register else 'login'}",
        headers={"X-CSRF-Token": csrf.json()["csrf_token"]},
        json=credentials,
    )
    assert response.status_code == (201 if register else 200), response.text
    return response.json()["csrf_token"]


def test_nonroot_setup_survives_container_recreation(tmp_path):
    storage = tmp_path / "data"
    storage.mkdir()
    mount = f"type=bind,source={storage},target=/app/data"
    try:
        # The same one-time preparation as Compose (PROJECT.md Commands).
        docker(
            "run", "--rm", "--user", "root", "--entrypoint", "chown",
            "--mount", mount, IMAGE, "-R", "10001:10001", "/app/data",
        )
        with running_container(storage) as (client, name):
            assert docker("exec", name, "id", "-u") != "0"
            original_container = docker("inspect", "--format", "{{.Id}}", name)
            assert client.get("/api/v1/employer").status_code == 401
            token = authenticate(client, register=True)
            expected_account = client.get("/api/v1/auth/me").json()
            assert client.post("/api/v1/setup", json=SETUP).status_code == 403
            response = client.post(
                "/api/v1/setup", headers={"X-CSRF-Token": token}, json=SETUP,
            )
            assert response.status_code == 201, response.text
            expected_employer = {
                "id": response.json()["employer_id"], **SETUP["employer"],
            }
            employer = client.get("/api/v1/employer")
            assert employer.status_code == 200, employer.text
            assert employer.json() == expected_employer
            saved_rows = setup_snapshot(name)
            assert (storage / "payroll.db").stat().st_uid == int(docker("exec", name, "id", "-u"))

        with running_container(storage) as (client, name):
            assert docker("inspect", "--format", "{{.Id}}", name) != original_container
            assert docker("exec", name, "id", "-u") != "0"
            assert client.get("/api/v1/employer").status_code == 401
            token = authenticate(client, register=False)
            assert client.get("/api/v1/auth/me").json() == expected_account
            employer = client.get("/api/v1/employer")
            assert employer.status_code == 200, employer.text
            assert employer.json() == expected_employer
            assert setup_snapshot(name) == saved_rows
            logout = client.post(
                "/api/v1/auth/logout", headers={"X-CSRF-Token": token},
            )
            assert logout.status_code == 204, logout.text
            assert client.get("/api/v1/employer").status_code == 401
    finally:
        docker(
            "run", "--rm", "--user", "root", "--entrypoint", "chown",
            "--mount", mount, IMAGE, "-R", f"{os.getuid()}:{os.getgid()}", "/app/data",
        )
        shutil.rmtree(storage)
