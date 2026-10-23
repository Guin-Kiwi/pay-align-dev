import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
HOOK = "https://api.render.com/deploy/srv-example?key=hook-secret"
APP = "https://payalign.example"

FAKE_CURL = """#!/bin/sh
printf '%s\\n' "$*" >> "$CURL_LOG"
printf '%s' "${CURL_BODY:-}"
exit "${CURL_EXIT:-0}"
"""


class ScriptRun:
    def __init__(self, tmp):
        self.bin = pathlib.Path(tmp) / "bin"
        self.bin.mkdir()
        curl = self.bin / "curl"
        curl.write_text(FAKE_CURL)
        curl.chmod(0o755)
        self.log = pathlib.Path(tmp) / "curl.log"

    def run(self, script, **env):
        base = {k: v for k, v in os.environ.items()
                if k not in ("RENDER_DEPLOY_HOOK_URL", "APP_URL")}
        base.update(PATH=f"{self.bin}{os.pathsep}{os.environ['PATH']}",
                    CURL_LOG=str(self.log), SMOKE_DELAY_SECONDS="0", **env)
        return subprocess.run(["bash", str(ROOT / "scripts" / script)],
                              capture_output=True, text=True, env=base)

    def curl_calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []


class DeployScriptTests(unittest.TestCase):
    def test_missing_hook_fails_without_calling_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = ScriptRun(tmp)
            result = run.run("deploy.sh")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("RENDER_DEPLOY_HOOK_URL", result.stderr)
            self.assertEqual(run.curl_calls(), [])

    def test_posts_to_the_hook_without_printing_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = ScriptRun(tmp)
            result = run.run("deploy.sh", RENDER_DEPLOY_HOOK_URL=HOOK)
            self.assertEqual(result.returncode, 0, result.stderr)
            [call] = run.curl_calls()
            self.assertIn("POST", call)
            self.assertIn(HOOK, call)
            self.assertNotIn("hook-secret", result.stdout + result.stderr)

    def test_rejected_hook_fails_the_deploy(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = ScriptRun(tmp)
            result = run.run("deploy.sh", RENDER_DEPLOY_HOOK_URL=HOOK, CURL_EXIT="22")
            self.assertNotEqual(result.returncode, 0)


class SmokeTestScriptTests(unittest.TestCase):
    def test_missing_app_url_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = ScriptRun(tmp)
            result = run.run("smoke-test.sh")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("APP_URL", result.stderr)

    def test_passes_when_health_answers_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = ScriptRun(tmp)
            result = run.run("smoke-test.sh", APP_URL=APP + "/", CURL_BODY='{"status":"ok"}')
            self.assertEqual(result.returncode, 0, result.stderr)
            [call] = run.curl_calls()
            self.assertIn(f"{APP}/health", call)

    def test_fails_after_the_last_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = ScriptRun(tmp)
            result = run.run("smoke-test.sh", APP_URL=APP, CURL_EXIT="7", SMOKE_ATTEMPTS="3")
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(len(run.curl_calls()), 3)
            self.assertIn(f"{APP}/health", result.stderr)

    def test_unexpected_health_body_is_not_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = ScriptRun(tmp)
            result = run.run("smoke-test.sh", APP_URL=APP, CURL_BODY="<html>starting</html>",
                             SMOKE_ATTEMPTS="2")
            self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
