---
name: ai-sdlc-0-bootstrap
description: Initialize or align a repository for AI-SDLC based on the intended system.
---

# PHASE 0 — BOOTSTRAP

## Goal

Align the repository with the **intended system** and prepare it for AI-SDLC.

---

## Required Input

Clarify with the user:

- system / app purpose
- framework

The language is Python (ADR-000); do not ask for it.

If unclear → ask before proceeding.

---

## Actions

### 1. Inspect repository

Check existing:

- structure (src/, tests/, docs/)
- dependency files
- existing code and tests

---

### 2. Align structure (minimal changes)

Ensure Clean Architecture:

src/app/domain  
src/app/application  
src/app/interfaces  
src/app/infrastructure  

tests/unit  
tests/integration  
tests/e2e  

Rules:

- the template ships this skeleton with `__init__.py` files (needed for test
  discovery) and `tests/unit/test_architecture.py`, which enforces the
  dependency rule; create only what is missing
- reuse existing structure if compatible
- do not duplicate or restructure unnecessarily

---

### 3. Dependencies

Check for:

requirements.txt  
pyproject.toml  

Rules:

- reuse if present
- create minimal file only if missing

The template ships a **Python + FastAPI default profile**: the devcontainer
image, `environments/python/`, `scripts/setup-python.sh` and the Python block
in `.gitignore`. Setup copies the profile's `requirements.txt`,
`.python-version` and `.vscode/launch.json` to the root.

Keep the profile; adjust `requirements.txt` to the chosen framework and commit
the copied root files. A non-Python project is outside this template's scope
(ADR-000); stop and ask the user.

---

### 4. Documentation

Ensure:

docs/PROJECT.md

Rules:

- update if exists
- create minimal version if missing

Content:

- purpose
- architecture
- structure
- resources (where non-code material lives; link reference documents)
- commands
- dependencies

---

### 5. Cleanup (only with user confirmation)

Identify:

- unused files
- irrelevant boilerplate
- mismatching structure
- template-only meta commentary that no longer applies once the project is
  established (e.g. `docs/PROJECT.md`'s "Complete this document during
  BOOTSTRAP" instruction line, README's template setup/"Create a project"
  steps) — replace with the real project's own content instead of removing
  the file
- template identity: README badges (AI-SDLC, DOI, arXiv), `CITATION.cff`,
  `.zenodo.json` and the owner in `.github/CODEOWNERS` describe the template,
  not the derived project — replace or remove them for the project
- `docs/future/`: roadmap notes for the template itself, not the project —
  remove them
- `README.md`: rewrite it for the project: what the app does and how to run
  it first, then a short "How this project was developed (AI-SDLC)" section
  linking `CONTRIBUTING.md`, `docs/specs/` and `docs/adr/`
- `LICENSE`: keep section 1 (CC BY 4.0 requires the template attribution to
  stay); ask the team which licence their own code uses and fill in section 2

Ask the user before removing anything.

---

## Evidence to provide

- clarified objective
- constraints
- assumptions
- smallest proposed slice
- open questions

---

## Output

Repository aligned with intended system.

Record phase 0 and status in `docs/TASKS.md` per `AGENTS.md`.

---
