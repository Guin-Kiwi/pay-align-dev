# AI-SDLC Project Template

[![AI-SDLC](https://img.shields.io/badge/AI--SDLC-v1.0.0-blue)](https://ai-sdlc.aisl.science)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22833065.svg)](https://doi.org/10.5281/zenodo.22833065)
[![arXiv](https://img.shields.io/badge/arXiv-2609.24348-b31b1b.svg)](https://doi.org/10.48550/arXiv.2609.24348)

Starter repository for student and teaching projects that use the AI-Assisted
Software Development Life Cycle (AI-SDLC).

The method is documented canonically in [AISL Docs](https://docs.aisl.science/learning-and-resources/ai-sdlc). This repository contains only the executable, repository-local
workflow artefacts. It does not contain a complete copy of the method or
application-specific code.

## How it works

Your agent does the work in phases, and you approve the results: BOOTSTRAP
(once, to define the project), then SPECIFY → DESIGN → DEVELOP → VALIDATE →
DEPLOY for each feature. Each phase is a skill in `skills/` that the agent
follows; `AGENTS.md` routes it there. Small fixes take a shorter Fast Track.
Tests come first (TDD), CI checks every pull request, and only real breakage
blocks a merge.

## What you build vs. what guides you

| | Paths | Licence |
|---|---|---|
| **Your project** (what is being built) | `src/app/` (domain, application, interfaces, infrastructure), `tests/`, `docs/PROJECT.md`, `docs/TASKS.md`, `docs/specs/`, `docs/adr/`, `README.md` | Your team's choice (`LICENSE` section 2) |
| **The AI-SDLC process** (how it is built) | `AGENTS.md`, `CONTRIBUTING.md`, `skills/`, `scripts/`, `.github/`, `environments/`, `docs/INDEX.json`, `docs/STANDARDS.md`, `docs/AGENT-GUIDANCE.md` | CC BY 4.0 (`LICENSE` section 1) |

Both stay in the repository: the process files are your evidence of TDD,
CI/CD and supervised agent use. Deployable artifacts contain only the app
(`.dockerignore` excludes the process files). Credit for the template:
Andreas Martin and Sandro Schwander (FHNW), CC BY 4.0, see `LICENSE`.

## Create a project

1. Select **Use this template** on GitHub and create a new repository. A
   one-time **"Define the project (BOOTSTRAP)"** issue opens with a checklist.
2. Open the new repository in GitHub Codespaces. Setup runs automatically and
   ends with `scripts/check-setup.sh`; run it again any time to confirm agents
   can find the skills.
3. Start BOOTSTRAP with your agent:
   - GitHub Copilot Chat: `/ai-sdlc`, then choose `bootstrap`
   - Claude Code: `/ai-sdlc-0-bootstrap`
   - Other agents: ask them to follow `AGENTS.md` and start phase 0
   BOOTSTRAP completes `docs/PROJECT.md`, then proposes removal or replacement
   of this template's own commentary, badges and citation files. The agent
   asks for confirmation before removing or replacing template identity.
4. For each feature or fix, ask your agent to start SPECIFY. It creates the
   branch and the spec; progress is recorded in `docs/TASKS.md`. A **Use
   case** issue is optional. `CONTRIBUTING.md` starts with a quick start and
   explains how branches, PRs and reviews work in a team.

## Day to day

[`CONTRIBUTING.md`](CONTRIBUTING.md) is the working guide: how big a change
is, branches and pull requests, choosing a model, where to find check results
and warnings, the human review report, and merging. Each step says where to
click and links to an official guide.

CI runs `scripts/check-lifecycle.sh` (are the AI-SDLC artefacts present and
consistent?) and `scripts/test.sh`, the project's test entrypoint: it runs
every test under `tests/` with pytest from the first commit, so each TDD step
shows in CI. `.github/workflows/cd.yml` is an inactive template, configured
during DEPLOY.

New to Git or VS Code? Try [GitHub Hello World](https://docs.github.com/en/get-started/using-github/hello-world),
the hands-on [GitHub Skills](https://skills.github.com/) courses and
[Source control in VS Code](https://code.visualstudio.com/docs/sourcecontrol/overview).

## Agent setup

The default stack profile is **Python + FastAPI**: Codespaces creates a Python
development container with Python, Pylance, debugging and GitHub Copilot
extensions, and `scripts/setup-python.sh` prepares `.venv`. This template
assumes Python ([ADR-000](docs/adr/ADR-000-python-as-project-language.md));
BOOTSTRAP keeps the profile and adjusts the framework. The default
terminal locale is English; the VS Code UI uses its own user display-language
setting.

Codespaces links the skills for all supported agents. Run
`bash scripts/setup-skills.sh` yourself when working outside Codespaces. Run
`bash scripts/setup-python.sh` again when the Python environment needs to be
recreated or refreshed.
Choose `copilot`, `codex`, `claude`, `cline`, `opencode`, `cursor`, `kiro`,
`junie`, `devin` or `all`. The script links to the canonical `skills/` directory and
falls back to copying if links are unavailable. Existing destinations are kept;
copies must be refreshed manually after skill changes. Verify discovery in your
agent; setup does not install or configure the agent itself.

For non-interactive setup, pass the same selection, for example `bash scripts/setup-skills.sh copilot`. `CLAUDE.md` (which imports `AGENTS.md`) is included in the repository; the `claude` and `all` selections recreate it if missing. Skill links are per-machine and ignored by git.

## Repository artefacts

- `AGENTS.md` — lifecycle router and guardrails (`CLAUDE.md` imports it)
- `CONTRIBUTING.md` — team workflow: change-size ladder, branches, PRs, agent
  git rules, repository setup
- `docs/INDEX.json` — map of phases, skills and review-gated files
- `docs/PROJECT.md` — project context and commands
- `docs/TASKS.md` — current lifecycle state
- `docs/specs/` — executable use-case specifications
- `docs/adr/` — architecture decision records and their template
- `docs/STANDARDS.md` — security and quality references (NIST SSDF, OWASP ASVS)
- `docs/AGENT-GUIDANCE.md` — worked examples for applying the agent rules
- `docs/future/` — non-binding roadmap notes
- `skills/ai-sdlc-*` — phase-specific execution guidance
- `.devcontainer/` — Codespaces and VS Code baseline
- `environments/python/` — default Python + FastAPI profile, including the
  source VS Code debug configuration
- `scripts/setup-skills.sh`, `scripts/setup-python.sh` — agent and environment setup
- `scripts/check-setup.sh` — confirms local setup worked
- `scripts/check-lifecycle.sh` — artefact consistency checks run by CI
- `scripts/test.sh` — project test entrypoint run by CI and release;
  `scripts/test-lifecycle.sh` and `scripts/tests/` test the template's own checks
- `scripts/pr_advisory.py` — non-blocking PR warnings (model tier, Fast Track scope)
- `scripts/sdlc.py review` — optional human review report, recorded in history
- `.vscode/tasks.json` — "AI-SDLC: Run checks" and "AI-SDLC: Human review report"
- `.github/` — Copilot instructions and `/ai-sdlc` prompt, CODEOWNERS, PR and
  use-case issue templates, CI, release, bootstrap-issue and CD workflows,
  importable rulesets
