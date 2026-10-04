import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import sdlc


def scripted(answers):
    it = iter(answers)
    return lambda prompt="": next(it)


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def make_repo(tmp):
    git(tmp, "init", "-q", "-b", "main")
    git(tmp, "config", "user.email", "ayla@example.com")
    git(tmp, "config", "user.name", "Ayla")
    git(tmp, "commit", "-q", "--allow-empty", "-m", "chore: base")
    git(tmp, "switch", "-q", "-c", "uc-042-login")
    with open(os.path.join(tmp, "app.py"), "w") as fh:
        fh.write("x = 1\n")
    git(tmp, "add", "app.py")
    git(tmp, "commit", "-q", "-m", "feat: login\n\nAgent-Model: m1\nAgent-Tier: standard")


GOOD = ["Added login endpoint", "yes", "partly", "Ran tests, tried a wrong password", ""]


class AskTests(unittest.TestCase):
    def test_required_text_repeats_until_answered(self):
        out = []
        answer = sdlc.ask_text("Q?", required=True, ask=scripted(["", "  ", "done"]), out=out.append)
        self.assertEqual(answer, "done")
        self.assertTrue(any("required" in line for line in out))

    def test_optional_text_defaults_to_none(self):
        self.assertEqual(sdlc.ask_text("Q?", required=False, ask=scripted([""]), out=lambda *_: None), "none")

    def test_choice_rejects_unknown_answers(self):
        answer = sdlc.ask_choice("Q?", ["yes", "partly", "no"], ask=scripted(["maybe", "Partly"]), out=lambda *_: None)
        self.assertEqual(answer, "partly")


class MessageTests(unittest.TestCase):
    def test_message_contains_answers_range_and_trailer(self):
        answers = dict(zip(sdlc.QUESTION_KEYS, ["A", "yes", "n.a.", "Ran tests", "none"]))
        msg = sdlc.build_message(answers, ["aaaaaaa1", "bbbbbbb2"], "Ayla <ayla@example.com>")
        self.assertTrue(msg.startswith("review: human review of 2 commits"))
        self.assertIn("What I checked myself: Ran tests", msg)
        self.assertIn("Reviewed-commits: aaaaaaa..bbbbbbb", msg)
        self.assertIn("Agent-Tier: none", msg)
        self.assertTrue(msg.rstrip().endswith("Reviewed-by: Ayla <ayla@example.com>"))


class ReviewFlowTests(unittest.TestCase):
    def test_refuses_without_terminal(self):
        out = []
        code = sdlc.review(cwd=".", ask=scripted([]), out=out.append, interactive=False)
        self.assertEqual(code, 1)
        self.assertIn("for humans", " ".join(out))

    def test_records_review_commit_and_stops(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_repo(tmp)
            with open(os.path.join(tmp, "staged.txt"), "w") as fh:
                fh.write("work in progress\n")
            git(tmp, "add", "staged.txt")
            out = []
            code = sdlc.review(cwd=tmp, ask=scripted(GOOD), out=out.append, interactive=True)
            message = git(tmp, "log", "-1", "--format=%B")
            files_in_review = git(tmp, "show", "--name-only", "--format=", "HEAD")
            still_staged = git(tmp, "diff", "--cached", "--name-only")
        self.assertEqual(code, 0)
        self.assertIn("Reviewed-by: Ayla <ayla@example.com>", message)
        self.assertIn("feat: login", " ".join(out))
        self.assertIn("Agent-Tier: standard", " ".join(out))
        self.assertEqual(files_in_review, "")
        self.assertEqual(still_staged, "staged.txt")
        self.assertIn("open your PR when ready", out[-1])
        self.assertNotIn("agent", out[-1].lower())

    def test_second_review_covers_only_new_commits(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_repo(tmp)
            sdlc.review(cwd=tmp, ask=scripted(GOOD), out=lambda *_: None, interactive=True)
            out = []
            code = sdlc.review(cwd=tmp, ask=scripted(GOOD), out=out.append, interactive=True)
        self.assertEqual(code, 0)
        self.assertIn("No new commits to review", " ".join(out))


if __name__ == "__main__":
    unittest.main()
