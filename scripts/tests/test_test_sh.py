import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]


def make_project(tmp, test_body, python_flags=""):
    root = pathlib.Path(tmp)
    (root / "scripts" / "tests").mkdir(parents=True)
    shutil.copy(ROOT / "scripts" / "test.sh", root / "scripts" / "test.sh")
    shutil.copy(ROOT / "pytest.ini", root / "pytest.ini")
    for stub in ("check-lifecycle.py", "test-lifecycle.py"):
        (root / "scripts" / stub).write_text("exit 0\n")
    (root / "scripts" / "tests" / "test_stub.py").write_text(
        "import unittest\n\nclass Stub(unittest.TestCase):\n    def test_ok(self):\n        pass\n")
    (root / "tests" / "unit").mkdir(parents=True)
    (root / "src" / "app").mkdir(parents=True)
    (root / "tests" / "unit" / "test_example.py").write_text(test_body)
    python = root / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text(f'#!/bin/sh\nexec "{sys.executable}" {python_flags} "$@"\n')
    python.chmod(0o755)
    
    # Install pytest in the test environment
    subprocess.run([sys.executable, "-m", "pip", "install", "pytest"], cwd=root, check=True)
    return root


def run_test_sh(root):
    # Ensure pytest is installed globally for the test
    subprocess.run([sys.executable, "-m", "pip", "install", "pytest"], check=True)
    return subprocess.run([sys.executable, str(root / "scripts" / "test.sh")], cwd=root,
                          capture_output=True, text=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})


class TestShTests(unittest.TestCase):
    def test_failing_pytest_style_test_fails_the_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(tmp, "def test_this_should_fail():\n    assert 1 == 2\n")
            result = run_test_sh(root)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("test_this_should_fail", result.stdout + result.stderr)

    def test_passing_pytest_style_test_passes_the_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(tmp, "def test_this_passes():\n    assert 1 == 1\n")
            result = run_test_sh(root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("1 passed", result.stdout)

    def test_missing_pytest_stops_with_setup_hint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(tmp, "def test_this_passes():\n    assert 1 == 1\n", python_flags="-S")
            result = run_test_sh(root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("bash scripts/setup-python.sh", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
