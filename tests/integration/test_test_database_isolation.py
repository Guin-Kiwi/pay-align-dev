import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_tests_never_use_the_developers_database(tmp_path):
    developer_database = tmp_path / "payroll.db"
    environment = {**os.environ, "DATABASE_URL": f"sqlite:///{developer_database}"}

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/integration/test_health.py"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert not developer_database.exists()
