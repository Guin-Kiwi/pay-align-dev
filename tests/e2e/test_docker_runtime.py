"""Run explicitly with TEST_DOCKER_IMAGE pointing to a locally built image."""

import os
import subprocess
import time
from contextlib import contextmanager
from uuid import uuid4

import httpx
import pytest

from tests.e2e.test_demo_flow import SETUP

IMAGE = os.environ.get("TEST_DOCKER_IMAGE")
pytestmark = pytest.mark.skipif(not IMAGE, reason="Set TEST_DOCKER_IMAGE to test a built image")


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
                pytest.fail(f"Container did not become healthy:\n{docker('logs', name)}")
            yield client, name
    finally:
        docker("rm", "--force", name)


def test_nonroot_server_saves_setup_to_prepared_bind_mount(tmp_path):
    storage = tmp_path / "data"
    storage.mkdir()
    mount = f"type=bind,source={storage},target=/app/data"
    # The same one-time preparation as Compose (PROJECT.md Commands).
    docker(
        "run", "--rm", "--user", "root", "--entrypoint", "chown",
        "--mount", mount, IMAGE, "-R", "10001:10001", "/app/data",
    )
    try:
        with running_container(storage) as (client, name):
            assert docker("exec", name, "id", "-u") != "0"
            response = client.post("/api/v1/setup", json=SETUP)
            assert response.status_code == 201, response.text
            assert client.get("/api/v1/employer").json() == {
                "id": response.json()["employer_id"], **SETUP["employer"],
            }
            docker(
                "exec", name, "python", "-c",
                "import sqlite3; "
                "db = sqlite3.connect('/app/data/payroll.db'); "
                "assert all(db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] == 1 "
                "for table in ('employers', 'employees', 'employments'))",
            )
            assert (storage / "payroll.db").stat().st_uid == int(docker("exec", name, "id", "-u"))
    finally:
        docker(
            "run", "--rm", "--user", "root", "--entrypoint", "chown",
            "--mount", mount, IMAGE, "-R", f"{os.getuid()}:{os.getgid()}", "/app/data",
        )
