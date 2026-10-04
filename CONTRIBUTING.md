# Contributing
<!-- Human review required: changes need a code owner's approval (.github/CODEOWNERS). -->

How people and coding agents work together in this repository. The lifecycle
itself is defined in `AGENTS.md`; this file covers team workflow.

## Quick start

1. **Start**: in the chat view type `/ai-sdlc` → `specify` (Copilot) or
   `/ai-sdlc-1-specify` (Claude Code) and describe the feature or fix. The
   agent creates the branch and the spec.
2. **Build**: continue with the next phases in the chat. Read each change in
   **Source Control** before it is committed.
3. **Share**: publish the branch, open a pull request on GitHub, read the
   `advisory` warnings, get one approval, then **Rebase and merge**.
4. **Finish**: back in VS Code, switch to `main` and select **Sync** to pull.

The sections below explain each step when you need more.

## How big is this change?

Pick the lowest level that fits.

| Level | What qualifies | Record it in |
|---|---|---|
| 1. Commit | A step inside already-scoped work: a test, an implementation step, a refactor | The commit, on the use case's branch |
| 2. Fast Track | A small correction within existing behaviour: a bug fix (start with a failing test), wording, config, docs | One line in the PR description or `docs/TASKS.md` |
| 3. Use case | Anything that adds or changes observable behaviour, i.e. something an acceptance criterion would describe | `docs/specs/UC-NNN-<NAME>.md` → branch → PR |
| 4. ADR | A consequential decision that is hard to reverse or spans use cases: data store, auth approach, framework, a break in the layer rules | `docs/adr/ADR-NNN-<title>.md`, Proposed until a human accepts it, usually inside a use case's PR |

Fast Track never covers new features, API or data changes, security,
dependencies or architecture. If a Fast Track grows into any of these, stop
and continue as a use case.

Borderline? If a teammate would need to agree on *what* it should do before
you build it, it is a use case. If they only need to check *how* you did it,
it is Fast Track.

## Working with an agent

Agent rules live in `AGENTS.md`, which every agent loads. This file is
written for humans. Your side of the loop:

1. **Start a phase**: in the chat view type `/ai-sdlc` (Copilot) or the
   phase skill, such as `/ai-sdlc-1-specify` (Claude Code).
2. **Pick the model** for the task (see "Choosing a model").
3. **Read the diff** before the work is committed: open the **Source Control**
   view and click each changed file.
4. **Run the checks** (see "Checks and what they mean").
5. **Record your review** when the work is finished (see "Human review report").

Guides: [Copilot Chat](https://code.visualstudio.com/docs/chat/chat-overview),
[Claude Code in VS Code](https://code.claude.com/docs/en/vs-code),
[stage and commit](https://code.visualstudio.com/docs/sourcecontrol/staging-commits).

## Choosing a model

The human picks the model; each skill's `index.json` gives a `model_tier`
hint. Switch models with the model picker under the chat box (Copilot) or
`/model` (Claude Code).

| Work | Tier |
|---|---|
| BOOTSTRAP, SPECIFY, DESIGN, ADRs: judgement and trade-offs | large |
| DEVELOP against a failing test, VALIDATE, DEPLOY | standard |
| Fast Track, single commits, docs, small refactors | small |

Start one tier lower than you think. If the same test still fails after two
fix attempts, or the agent asks questions the spec already answers, move up a
tier. Move down when a task turns out to be Fast Track.

## Use cases, branches and pull requests

- The agent creates the branch when SPECIFY starts: `uc-NNN-<short-name>`
  for a use case, `fix-<short-name>` or `docs-<short-name>` for Fast Track.
- Issues are optional. If you want the team to see planned work on GitHub,
  open a **Use case** issue first (**Issues → New issue → Use case**; your
  agent can draft the text) and give the agent its number: issue #42 →
  `docs/specs/UC-042-<NAME>.md`. Without an issue, the agent takes the next
  free number. Pick one way as a team so numbers do not clash.
- One use case per branch and per PR. With an issue, the PR body says
  `Closes #42`.
- On a branch, `docs/TASKS.md` describes that branch's use case only. Before
  merging, update the branch from `main` and reconcile `docs/TASKS.md` and
  any UC or ADR numbers with what `main` already has.
- ADR numbers: take the next unused number on `main`. CI rejects duplicates.
- Change shared files (`AGENTS.md`, `docs/PROJECT.md`, `docs/INDEX.json`,
  `.github/`) in their own small PR, not mixed into feature work.
- App code, including app scripts and CLIs, lives under `src/app/` and its
  tests under `tests/`. `scripts/` is AI-SDLC tooling; do not put app code there.

Guides: [create an issue](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/creating-an-issue),
[branches in VS Code](https://code.visualstudio.com/docs/sourcecontrol/branches-worktrees),
[create a pull request](https://docs.github.com/en/pull-requests/how-tos/create-pull-requests/creating-a-pull-request),
[issues and pull requests from inside VS Code](https://code.visualstudio.com/docs/sourcecontrol/github).

## Checks and what they mean

| Severity | Effect | Used for |
|---|---|---|
| Block | CI fails; the PR cannot merge | Real breakage: missing or inconsistent lifecycle files, a filled-in UC or ADR template, duplicate UC/ADR numbers, failing tests |
| Warn | Yellow annotation on the PR; merging is allowed | A small-tier commit changed use cases, ADRs, `AGENTS.md`, `CONTRIBUTING.md`, workflows or rulesets; any agent commit changed a review-gated file (`docs/INDEX.json`); a Fast Track branch exceeded its scope; a skill lacks `model_tier` |
| Info | Shown in the CI summary only | An agent commit without `Agent-Tier`; a large tier on a Fast Track branch |

Checks run on GitHub: the `structure` job blocks, the `advisory` job only
informs.

- **Run the checks yourself** before you push: **Terminal → Run Task… →
  AI-SDLC: Run checks**, or `bash scripts/test.sh`. Lines starting with `✗`
  block; lines starting with `⚠` are warnings.
- **Find the warnings on a PR.** The `advisory` check always shows a green
  tick, even when it has warnings, so open it to look: **Checks** tab →
  **advisory**. The run summary lists warnings under **Annotations** and in
  the **PR advisory** section.
- **Find out why `structure` failed**: click **Details** next to the red ✗,
  expand the failed step and look for the line starting with `✗`. Run the
  checks locally to reproduce it.

Guides: [status checks](https://docs.github.com/en/pull-requests/reference/status-checks),
[workflow run logs](https://docs.github.com/en/actions/how-tos/monitor-workflows/use-workflow-run-logs),
[VS Code tasks](https://code.visualstudio.com/docs/debugtest/tasks).

## Human review report

When a set of agent loops or a conversation has concluded and you want your
check on record, run **Terminal → Run Task… → AI-SDLC: Human review report**
(or `python3 scripts/sdlc.py review`) and answer in the terminal. It is optional and never blocks anyone.

It summarises the commits since your last report, asks five questions (what
changed, whether you read every file, whether the tests check the acceptance
criteria, what you checked yourself, what the PR reviewer should look at) and
records your answers as a `review:` commit ending in `Reviewed-by:`. Specific
answers to "what did you check yourself" are the evidence; "looked fine" is
not. Answering "partly" is fine and tells the PR reviewer where to look.

A review recorded after a flagged commit marks it as human-reviewed: the PR
advisory then shows "human-reviewed by <name>" instead of a warning. This
only settles the advisory; the teammate's approval is still required.

## Review and merge

- Every change to `main` goes through a PR with one teammate's approval and
  passing CI, and the branch must be up to date with `main`.
- Files listed in `.github/CODEOWNERS` also need a code owner's review.
- The reviewer approves under **Files changed → Review changes → Approve**.
- The author merges after approval, using **Rebase and merge** (choose it
  from the arrow next to the merge button).
- **`docs/TASKS.md` conflicts** are expected when two branches run in
  parallel: each branch records its own use case there. To resolve, keep
  `main`'s version, then put back your branch's PHASE, STATUS and current use
  case. You can ask your agent to do this.
- If the `advisory` job warns, the reviewer looks harder at the flagged files,
  ideally with a second review by a larger model (Copilot code review on the
  PR, or an agent's code-review command), and leaves a one-to-three line
  "what I checked" comment with the approval.

Guides: [review a pull request](https://docs.github.com/en/pull-requests/how-tos/review-pull-requests/reviewing-proposed-changes-in-a-pull-request),
[merge a pull request](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/merging-a-pull-request).

## Commits

- Keep the TDD steps as separate commits (failing test, then implementation,
  then refactor). PRs are **rebase-merged** so this history stays on `main`
  as evidence.
- Use conventional prefixes: `feat:`, `fix:`, `test:`, `refactor:`, `docs:`,
  `ci:`, `chore:`, and `review:` for recorded human reviews.
- Commits written by a coding agent end with two trailers, which the PR
  advisory reads:

  ```
  Agent-Model: <model name>
  Agent-Tier: small | standard | large
  ```

  Human-written commits may add `Agent-Tier: none`; a commit without the
  trailer is assumed to be human-written.

## Repository setup

Rulesets are not copied when a repository is created from the template.
Import them once under **Settings → Rules → Rulesets → New ruleset → Import a
ruleset**, from `.github/rulesets/`
([guide](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/managing-rulesets-for-a-repository)):

- `main-team.json` for team repositories: PRs with one approval, code-owner
  review, up-to-date branches, passing CI, rebase-merge only, no force pushes.
  Updating a branch after approval reruns CI but keeps the approval.
- `main-solo.json` for single-person repositories: no force pushes or
  deletion of `main`. Working directly on `main` is allowed; tell your agent
  when it may commit there.
- Optional, only if you publish releases: `release-tags.json` lets only
  admins create, move or delete `v*` tags.

Rulesets on private repositories need GitHub Pro on the owner's account
(included in the GitHub Student Developer Pack). Also enable secret scanning
with push protection and Dependabot alerts under **Settings → Code security**,
and **Automatically delete head branches** under **Settings → General**.
