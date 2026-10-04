import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pr_advisory as pa


def commit(message, files, sha="abc1234def"):
    return {"sha": sha, "message": message, "files": files}


def write(path, text):
    with open(path, "w") as fh:
        fh.write(text)


class TrailerTests(unittest.TestCase):
    def test_reads_agent_tier_and_model(self):
        msg = "feat: x\n\nbody\n\nAgent-Model: claude-opus-5-5\nAgent-Tier: Large\n"
        self.assertEqual(pa.tier_of(msg), "large")
        self.assertEqual(pa.model_of(msg), "claude-opus-5-5")

    def test_missing_trailers(self):
        self.assertIsNone(pa.tier_of("fix: y"))
        self.assertFalse(pa.is_agent_commit("fix: y"))

    def test_co_author_marks_agent_commit(self):
        msg = "feat: x\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n"
        self.assertTrue(pa.is_agent_commit(msg))
        self.assertIsNone(pa.tier_of(msg))

    def test_human_tier_none_is_not_agent(self):
        self.assertFalse(pa.is_agent_commit("docs: z\n\nAgent-Tier: none\n"))


class AdviseTests(unittest.TestCase):
    def test_clean_pr_has_no_findings(self):
        findings = pa.advise(
            [commit("feat: a\n\nAgent-Tier: standard\n", ["src/app/x.py"])],
            [("M", "src/app/x.py")],
            "uc-042-login",
        )
        self.assertEqual(findings, [])

    def test_small_tier_on_high_judgement_file_warns(self):
        findings = pa.advise(
            [commit("docs: spec\n\nAgent-Tier: small\n", ["docs/specs/UC-042-LOGIN.md"])],
            [("A", "docs/specs/UC-042-LOGIN.md")],
            "uc-042-login",
        )
        self.assertEqual(len(findings), 1)
        level, text = findings[0]
        self.assertEqual(level, "warning")
        self.assertIn("review thoroughly", text)
        self.assertIn("docs/specs/UC-042-LOGIN.md", text)

    def test_standard_tier_on_high_judgement_file_is_fine(self):
        findings = pa.advise(
            [commit("docs: adr\n\nAgent-Tier: standard\n", ["docs/adr/ADR-003-db.md"])],
            [("A", "docs/adr/ADR-003-db.md")],
            "uc-042-login",
        )
        self.assertEqual(findings, [])

    def test_agent_commit_without_tier_is_noted(self):
        findings = pa.advise(
            [commit("feat: a\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n", ["src/a.py"])],
            [("M", "src/a.py")],
            "uc-042-login",
        )
        self.assertEqual([level for level, _ in findings], ["notice"])
        self.assertIn("Agent-Tier", findings[0][1])

    def test_fast_track_touching_dependencies_warns(self):
        findings = pa.advise(
            [commit("fix: bump\n\nAgent-Tier: none\n", ["requirements.txt"])],
            [("M", "requirements.txt")],
            "fix-typo",
        )
        self.assertEqual([level for level, _ in findings], ["warning"])
        self.assertIn("Fast Track scope exceeded", findings[0][1])
        self.assertIn("requirements.txt", findings[0][1])

    def test_fast_track_adding_use_case_warns(self):
        findings = pa.advise(
            [commit("docs: uc\n\nAgent-Tier: none\n", ["docs/specs/UC-050-X.md"])],
            [("A", "docs/specs/UC-050-X.md")],
            "docs-x",
        )
        self.assertIn("Fast Track scope exceeded", findings[0][1])

    def test_fast_track_small_code_change_is_fine(self):
        findings = pa.advise(
            [commit("fix: off by one\n\nAgent-Tier: small\n", ["src/app/x.py", "tests/unit/test_x.py"])],
            [("M", "src/app/x.py"), ("M", "tests/unit/test_x.py")],
            "fix-off-by-one",
        )
        self.assertEqual(findings, [])

    def test_large_tier_on_fast_track_is_info_only(self):
        findings = pa.advise(
            [commit("fix: typo\n\nAgent-Tier: large\n", ["README.md"])],
            [("M", "README.md")],
            "docs-typo",
        )
        self.assertEqual([level for level, _ in findings], ["notice"])
        self.assertIn("smaller tier", findings[0][1])


GATED = ["AGENTS.md", "CLAUDE.md", ".github/workflows/"]
REVIEW = "review: human review of 1 commits\n\nAgent-Tier: none\nReviewed-by: Ayla <ayla@example.com>\n"


class ReviewGatedTests(unittest.TestCase):
    def test_agent_change_to_review_gated_file_warns(self):
        findings = pa.advise(
            [commit("docs: rules\n\nAgent-Tier: standard\n", ["AGENTS.md"])],
            [("M", "AGENTS.md")], "uc-042-login", gated=GATED,
        )
        self.assertEqual([level for level, _ in findings], ["warning"])
        self.assertIn("review-gated", findings[0][1])
        self.assertIn("not yet human-reviewed", findings[0][1])
        self.assertIn("sdlc.py review", findings[0][1])

    def test_gated_directory_prefix_matches(self):
        findings = pa.advise(
            [commit("ci: x\n\nAgent-Tier: large\n", [".github/workflows/ci.yml"])],
            [("M", ".github/workflows/ci.yml")], "uc-042-login", gated=GATED,
        )
        self.assertEqual([level for level, _ in findings], ["warning"])

    def test_human_change_to_review_gated_file_is_not_flagged(self):
        findings = pa.advise(
            [commit("docs: rules\n\nAgent-Tier: none\n", ["AGENTS.md"])],
            [("M", "AGENTS.md")], "uc-042-login", gated=GATED,
        )
        self.assertEqual(findings, [])

    def test_later_review_turns_gated_warning_into_notice(self):
        findings = pa.advise(
            [commit("docs: rules\n\nAgent-Tier: standard\n", ["AGENTS.md"], sha="aaaaaaa1"),
             commit(REVIEW, [], sha="bbbbbbb2")],
            [("M", "AGENTS.md")], "uc-042-login", gated=GATED,
        )
        self.assertEqual([level for level, _ in findings], ["notice"])
        self.assertIn("human-reviewed by Ayla in bbbbbbb", findings[0][1])

    def test_earlier_review_does_not_cover_later_change(self):
        findings = pa.advise(
            [commit(REVIEW, [], sha="bbbbbbb2"),
             commit("docs: rules\n\nAgent-Tier: standard\n", ["AGENTS.md"], sha="aaaaaaa1")],
            [("M", "AGENTS.md")], "uc-042-login", gated=GATED,
        )
        self.assertEqual([level for level, _ in findings], ["warning"])

    def test_later_review_also_covers_small_tier_warning(self):
        findings = pa.advise(
            [commit("docs: spec\n\nAgent-Tier: small\n", ["docs/specs/UC-042-LOGIN.md"]),
             commit(REVIEW, [], sha="ccccccc3")],
            [("A", "docs/specs/UC-042-LOGIN.md")], "uc-042-login", gated=GATED,
        )
        self.assertEqual([level for level, _ in findings], ["notice"])
        self.assertIn("human-reviewed by Ayla", findings[0][1])

    def test_small_tier_on_gated_file_outside_high_judgement_warns_once(self):
        findings = pa.advise(
            [commit("chore: x\n\nAgent-Tier: small\n", ["CLAUDE.md"])],
            [("M", "CLAUDE.md")], "uc-042-login", gated=GATED,
        )
        self.assertEqual([level for level, _ in findings], ["warning"])

    def test_loads_gated_paths_from_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "docs"))
            write(os.path.join(tmp, "docs", "INDEX.json"),
                  '{"review_gated": {"rule": "r", "paths": ["AGENTS.md", ".github/rulesets/"]}}')
            self.assertEqual(pa.load_gated(tmp), ["AGENTS.md", ".github/rulesets/"])
            self.assertEqual(pa.load_gated(os.path.join(tmp, "missing")), [])


class GitIntegrationTests(unittest.TestCase):
    def test_commits_are_oldest_first(self):
        with tempfile.TemporaryDirectory() as repo:
            def git(*args):
                return subprocess.run(["git", "-C", repo, *args], check=True,
                                      capture_output=True, text=True).stdout.strip()
            git("init", "-q", "-b", "main")
            git("config", "user.email", "t@example.com")
            git("config", "user.name", "T")
            git("commit", "-q", "--allow-empty", "-m", "chore: base")
            base = git("rev-parse", "HEAD")
            git("commit", "-q", "--allow-empty", "-m", "first")
            git("commit", "-q", "--allow-empty", "-m", "second")
            commits, _ = pa.collect(base, "HEAD", cwd=repo)
        self.assertEqual([c["message"].strip() for c in commits], ["first", "second"])

    def test_collects_commits_and_files_from_git(self):
        with tempfile.TemporaryDirectory() as repo:
            def git(*args):
                return subprocess.run(["git", "-C", repo, *args], check=True,
                                      capture_output=True, text=True).stdout.strip()
            git("init", "-q", "-b", "main")
            git("config", "user.email", "t@example.com")
            git("config", "user.name", "T")
            write(os.path.join(repo, "a.txt"), "a\n")
            git("add", ".")
            git("commit", "-q", "-m", "chore: base")
            base = git("rev-parse", "HEAD")
            os.makedirs(os.path.join(repo, "docs", "adr"))
            write(os.path.join(repo, "docs", "adr", "ADR-001-x.md"), "x\n")
            git("add", ".")
            git("commit", "-q", "-m", "docs: adr\n\nAgent-Tier: small")
            head = git("rev-parse", "HEAD")

            commits, changed = pa.collect(base, head, cwd=repo)

        self.assertEqual(len(commits), 1)
        self.assertEqual(commits[0]["files"], ["docs/adr/ADR-001-x.md"])
        self.assertEqual(pa.tier_of(commits[0]["message"]), "small")
        self.assertEqual(changed, [("A", "docs/adr/ADR-001-x.md")])


if __name__ == "__main__":
    unittest.main()
