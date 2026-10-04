---
name: ai-sdlc-4-validate
description: Verify repository readiness for release.
---

# PHASE 4 — VALIDATE

## Fast Track

Run planned checks; record results, omitted checks with reasons, and phase 4.
Skip the release-readiness checklist below; do not claim full release readiness.
Required CI/review remain; no incidental release or deployment.

## Goal

Verify that the repository is ready for its declared release path.

Focus on **checking existing artifacts**.

---

## Source of Truth

docs/TASKS.md  
docs/PROJECT.md  

---

## Steps

### 1. Run Local Tests

Run the project-specific unit and integration test commands documented in
`docs/PROJECT.md`.

Verify:

- unit tests pass
- integration tests pass

---

### 2. Verify E2E Tests when declared

If `docs/PROJECT.md` declares an E2E command or an E2E release requirement,
check:

tests/e2e/

Extend existing tests if needed. If E2E is not declared, record it as not
applicable rather than inventing an application-level test.

---

### 3. Verify the declared artifact

If `docs/PROJECT.md` declares a container artifact, check:

Dockerfile

Verify the container builds and starts the application, and that the image
contains only the app (`src/`, runtime dependencies, `LICENSE`); the root
`.dockerignore` already excludes the process files. If no container or other
build artifact is declared, record the artifact check as not applicable.

---

### 4. Verify CI

Check:

.github/workflows/ci.yml

CI and release run `scripts/test.sh`. Create or update it so it runs:

- unit tests
- integration tests

using the commands documented in `docs/PROJECT.md`. Do not add a separate test
workflow. `scripts/test.sh` ships running `tests/` with `pytest`, and CI installs
the project's requirements first.

---

### 5. Verify Release Workflow

Check:

.github/workflows/release.yml

Verify it runs `scripts/test.sh` and publishes the artifact declared in
`docs/PROJECT.md`, when one exists. Verify the declared E2E checks there as
well. A template repository with no application artifact may publish a source
release and record container/E2E checks as not applicable.

Create only if missing.

---

## Rules

- Prefer **verifying and extending existing artifacts**.
- Create files only if they do not exist.
- Avoid duplicate workflows.

---

## Evidence to provide

- summary of what changed
- what was validated
- what remains out of scope
- recommended next slice

---

## Output

Unit and integration tests pass.

Repository verified.

Write the actual evidence (checks run, results, links) into the active UC
file's "Evidence" section, so it stays with the use case after
`docs/TASKS.md` moves on. Record phase 4 and status in `docs/TASKS.md` per
`AGENTS.md`.
