# AGENTS.md — AI-SDLC Router

Repository state lives in:

`docs/TASKS.md`

Maintain `docs/TASKS.md`: PHASE = selected phase; STATUS = ready, in-progress,
done or blocked. Set in-progress on entry, done only after the phase output is
verified, or blocked with a reason. Keep PHASE on completion; an explicitly
selected next phase starts as ready. Changes to this router require human review.

---

This repository is an **AI-assisted SDLC template**.
It guides both humans and coding agents through small, testable, reviewable
software delivery steps.

## Core principles
- **AI-SDLC**
- **TDD**
- **Clean Architecture**
- **Small Vertical Slices**

---

Phases may be **skipped or repeated**.

Typical iteration:

SPECIFY → DESIGN → DEVELOP → VALIDATE  
VALIDATE → SPECIFY (iteration)  
DEPLOY → SPECIFY (feedback)

---

## Fast Track

- Small corrections only; no feature, API, data, security, dependency or architecture changes.
- Record scope, reason, acceptance and checks in the existing UC or `docs/TASKS.md`.
- Shorten SPECIFY; skip DESIGN with a reason. Scope grows → regular flow.
- Keep required CI and review. Release/deployment still require authorization.

## Collaboration

- Human-approved decisions → ADR; current architecture → `docs/PROJECT.md`.
- Durable rules + ADR links → `AGENTS.md`, with human approval/review.
- Update related files together; preserve decision history and reconcile parallel changes.
- `CONTRIBUTING.md` is the team workflow for humans; agents do not need to read it.
- App code goes in `src/app/`, its tests in `tests/`; `scripts/` and `skills/` are process tooling (`docs/INDEX.json` "project" vs "process").

## Context Load Order

Before making any change, load context in this order:

0. `docs/INDEX.json` — machine-readable map of phases, skills and which files
  need human review before editing; load this first.
1. `docs/TASKS.md`
2. `docs/PROJECT.md`
3. `docs/specs/UC-[NNN]-[NAME].md` (or the eligible Fast Track task entry)

If these sources conflict:
- `docs/TASKS.md` determines current execution priority/status
- `docs/PROJECT.md` defines project-wide constraints
- the active use-case spec defines slice-specific requirements
- if still unclear, stop and ask the human

External knowledge may support implementation, but repo-local documents are the
primary source of truth.

---

## Phase → Skill

0 → skills/ai-sdlc-0-bootstrap  
1 → skills/ai-sdlc-1-specify  
2 → skills/ai-sdlc-2-design  
3 → skills/ai-sdlc-3-develop  
4 → skills/ai-sdlc-4-validate  
5 → skills/ai-sdlc-5-deploy  

---

## Commands

Use the project-specific install, test, run and release commands documented in
`docs/PROJECT.md`. The language is Python
([ADR-000](docs/adr/ADR-000-python-as-project-language.md)). Do not assume a
framework or deployment platform before the project context has been completed.

---

## Agent operating rules

### 1) Work in the smallest useful slice
Prefer the smallest end-to-end increment that produces observable value.
Do not mix unrelated changes in one step.

### 2) Follow TDD
When code changes are required:
1. write or identify the test first
2. implement the minimal change to pass
3. refactor while preserving behavior

If the repository is not yet at a coding phase, produce only the minimal
documentation or planning artifact required by the current phase.

### 3) Respect Clean Architecture
Keep business rules independent from frameworks, UI, databases, and delivery
mechanisms. Avoid coupling decisions that reduce future flexibility without
explicit justification.

### 4) Keep artifacts minimal but sufficient
Create only artifacts that directly support execution, clarity, validation, or
handoff. Do not create ceremonial documentation.

### 5) Ground work in explicit requirements
For every meaningful task, identify:
- the source requirement
- the intended outcome
- the evidence that will show completion

Do not invent hidden requirements.
If you must assume something, label it clearly as an assumption.

### 6) Show reasoning through evidence, not verbosity
Prefer:
- acceptance criteria
- tests
- checklists
- diffs
- traceable notes

over long freeform explanations.

## Definition of done for any agent step
A step is only done when all applicable items are true:

- the task is aligned with the current phase
- the change is scoped to one small slice
- relevant requirements are referenced
- assumptions are called out
- tests/checks/review evidence are included where applicable
- `bash scripts/test.sh` passes
- no unresolved ambiguity is hidden
- risky actions were escalated when required
- the repository remains coherent for the next agent or human

Do not report completion based only on “files were edited”.

## Stop-and-ask triggers
Stop and ask the human before proceeding if any of the following occur:

- requirements are ambiguous or conflicting
- the requested change spans multiple slices and prioritization is unclear
- architecture implications are non-trivial
- a change would alter public interfaces, trust boundaries, or security posture
- secrets, credentials, or production-like sensitive data are involved
- the repo instructions conflict with external best practices in a way that affects delivery
- validation criteria are missing and cannot be inferred safely
- the task requires permissions or actions that are unavailable
- an unresolved assumption would change behavior, scope, or architecture if wrong
- the current skill's `model_tier` is above yours, or the same test still fails after two fix attempts

When stopping, present:
- what is unclear
- what options exist
- your recommended next step

Agents should optimize for reviewability, not autonomy for its own sake.

## Git and review

- Work on the current use case's or Fast Track's branch; commit to `main` only when a human allows it in this session (e.g. a solo repository).
- Never push, merge, force-push or delete branches unless a human asks in this session.
- End every commit with `Agent-Model: <model>` and `Agent-Tier: small|standard|large`.
- When a use case or conversation concludes, add once, without waiting: "Optional: run
  `python3 scripts/sdlc.py review` to make your human check verifiable." Never run it yourself or write a `Reviewed-by:` line.
- Parallel agents each use their own `git worktree`.

## Security and quality expectations

See `docs/STANDARDS.md` for the standing security/quality checklist (least
privilege, no hardcoded secrets, input validation, traceability) and
`docs/AGENT-GUIDANCE.md` for supplementary practices not already covered above.

## Rules

- Use the language of the current user prompt for all communication and all
  natural-language artifacts. Do not default to the language of earlier
  messages.
- Update existing artifacts; create only what is missing.
- Avoid unnecessary comments in code.
- Read the [canonical AI-SDLC documentation](https://docs.aisl.science/learning-and-resources/ai-sdlc)
  when terminology or lifecycle responsibilities are unclear.
- For standards and supporting rationale, see:
  - `docs/STANDARDS.md`
  - `docs/AGENT-GUIDANCE.md`

If requirements or architecture are unclear → ask the user.
