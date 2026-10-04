---
name: ai-sdlc-1-specify
description: Create or update a minimal use case specification.
---

# PHASE 1 — SPECIFY

## Fast Track

Use the existing UC or task entry per `AGENTS.md`; no new UC required.
If on `main`, create and switch to a branch `fix-<short-name>` or
`docs-<short-name>` first. In `docs/TASKS.md`, set "Current Use Case" to
`Fast Track: <short description>`. Record acceptance and planned checks, then
phase 1.
Skip the full UC steps below.

## Goal

Create or update a **minimal use case specification**.

---

## Input

User story or feature description.

If missing → ask the user.

---

## Use Case File

docs/specs/UC-[NNN]-[NAME].md

Rules:

- NNN = the GitHub issue number if the user gives one (issue #42 → 042),
  otherwise the next sequential number (001, 002, …)
- NAME = short uppercase identifier
- words separated with `-`

Determine the next number by scanning:

docs/specs/

If a UC for the feature already exists → **update it instead of creating a new one**.

---

## Branch

If on `main`, create and switch to `uc-NNN-<short-name>` (lowercase, same
NNN as the UC file) before writing anything. On an existing use-case branch,
stay on it.

---

## Steps

1. Open template

docs/specs/UC-TEMPLATE.md

2. Create or update the UC with minimal content, following the template's
   sections:

- Goal
- Business value
- Scope (in / out)
- Actors
- Preconditions
- Trigger
- Main flow
- Alternate / edge flows
- Errors / failure cases
- Acceptance criteria
- Security / trust-boundary notes
- Validation plan
- Open questions / assumptions
- Notes for implementation

Do not add unnecessary text. Write "none" for sections that don't apply.

---

## Rules

- Prefer **updating existing UC files**.
- Create a new UC only if none exists.
- Do not invent functionality.
- Ask the user if requirements are unclear.
- Do **not generate code or tests**.

---

## Evidence to provide

- acceptance criteria
- boundaries
- interfaces or components affected
- risks / tradeoffs
- validation approach

---

## Output

UC specification created or updated.

Record phase 1 and status in `docs/TASKS.md` per `AGENTS.md`.
