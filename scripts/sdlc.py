#!/usr/bin/env python3
"""AI-SDLC helper commands.

Human review required: changes need a code owner's approval (.github/CODEOWNERS).
This records human evidence: agents must never run it or weaken its checks.

  python3 scripts/sdlc.py review   Record a human review of recent work.
"""

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pr_advisory import model_of, tier_of

QUESTION_KEYS = ["changed", "read_all", "tests_match", "checked", "for_reviewer"]

INTRO = (
    "Human review report\n"
    "This records what you checked, so your review can be verified later by your\n"
    "team, the PR reviewer or an assessor. Be specific; \"partly\" is a fine answer.\n"
)


def ask_text(question, required, ask=input, out=print, hint=None):
    out(question)
    if hint:
        out(f"  ({hint})")
    while True:
        answer = ask("> ").strip()
        if answer:
            return answer
        if not required:
            return "none"
        out("  An answer is required.")


def ask_choice(question, choices, ask=input, out=print):
    out(f"{question} [{'/'.join(choices)}]")
    while True:
        answer = ask("> ").strip().lower()
        if answer in choices:
            return answer
        out(f"  Please answer one of: {', '.join(choices)}.")


def build_message(answers, shas, reviewer):
    first, last = shas[0][:7], shas[-1][:7]
    return (
        f"review: human review of {len(shas)} commits ({first}..{last})\n\n"
        f"What changed: {answers['changed']}\n"
        f"Read the changes in every file: {answers['read_all']}\n"
        f"Tests check the acceptance criteria: {answers['tests_match']}\n"
        f"What I checked myself: {answers['checked']}\n"
        f"For the PR reviewer: {answers['for_reviewer']}\n\n"
        f"Reviewed-commits: {first}..{last}\n"
        "Agent-Tier: none\n"
        f"Reviewed-by: {reviewer}\n"
    )


def _git(cwd, *args, check=True):
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()


def _start_point(cwd):
    last_review = _git(cwd, "log", "-1", "--format=%H", "--grep=^Reviewed-by:")
    if last_review:
        return last_review
    branch = _git(cwd, "rev-parse", "--abbrev-ref", "HEAD")
    for base in ("origin/main", "main"):
        if _git(cwd, "rev-parse", "--verify", "--quiet", base, check=False):
            if branch != "main":
                return _git(cwd, "merge-base", base, "HEAD")
    count = int(_git(cwd, "rev-list", "--count", "HEAD"))
    return "HEAD~10" if count > 10 else None


def _commits_since(cwd, start):
    rng = f"{start}..HEAD" if start else "HEAD"
    shas = _git(cwd, "rev-list", "--reverse", "--no-merges", rng).split()
    commits = []
    for sha in shas:
        message = _git(cwd, "log", "-1", "--format=%B", sha)
        files = _git(cwd, "show", "--name-only", "--format=", sha).split()
        commits.append({"sha": sha, "message": message, "files": files})
    return commits


def _summarise(commits, out):
    out(f"Commits since your last review: {len(commits)}")
    for c in commits:
        subject = c["message"].splitlines()[0] if c["message"] else ""
        tier = tier_of(c["message"]) or "unknown"
        model = model_of(c["message"])
        who = f"Agent-Tier: {tier}" + (f", {model}" if model else "")
        out(f"  {c['sha'][:7]}  {subject}  [{who}; {len(c['files'])} files]")
    out("")


def review(cwd=".", ask=input, out=print, interactive=None):
    if interactive is None:
        interactive = sys.stdin.isatty()
    if not interactive:
        out("This report is for humans: run it yourself in a terminal "
            "(python3 scripts/sdlc.py review or the VS Code task).")
        return 1

    out(INTRO)
    commits = _commits_since(cwd, _start_point(cwd))
    if not commits:
        out("No new commits to review since your last review.")
        return 0
    _summarise(commits, out)

    answers = {
        "changed": ask_text("1. In your own words, what changed?", True, ask, out),
        "read_all": ask_choice("2. Did you read the changes in every file?",
                               ["yes", "partly", "no"], ask, out),
        "tests_match": ask_choice("3. Do the tests check the use case's acceptance criteria?",
                                  ["yes", "partly", "no", "n.a."], ask, out),
        "checked": ask_text("4. What did you check or try yourself?", True, ask, out,
                            hint="for example: ran the tests, tried the feature with bad input, "
                                 "clicked through the screen. Name what you did"),
        "for_reviewer": ask_text("5. Anything the PR reviewer should look at?", False, ask, out,
                                 hint="press Enter for none"),
    }

    name = _git(cwd, "config", "user.name")
    email = _git(cwd, "config", "user.email")
    message = build_message(answers, [c["sha"] for c in commits], f"{name} <{email}>")
    tree = _git(cwd, "rev-parse", "HEAD^{tree}")
    parent = _git(cwd, "rev-parse", "HEAD")
    new = subprocess.run(["git", "commit-tree", tree, "-p", parent],
                         cwd=cwd, input=message, capture_output=True, text=True, check=True).stdout.strip()
    _git(cwd, "update-ref", "-m", "sdlc review", "HEAD", new, parent)
    out(f"Review recorded as commit {new[:7]}. Next: open your PR when ready.")
    return 0


def main(argv):
    if len(argv) == 2 and argv[1] == "review":
        return review()
    print(__doc__.strip())
    return 0 if len(argv) == 1 else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
