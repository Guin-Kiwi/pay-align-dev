---
name: ai-sdlc-5-deploy
description: Verify or collaboratively define the deployment workflow.
disable-model-invocation: true
---

# PHASE 5 — DEPLOY

## Goal

Verify the **continuous deployment workflow** for the validated artifact.

Deployment is defined **together with the user**.

---

## Check

Inspect:

.github/workflows/

If a CD workflow exists:

- verify trigger
- verify deployment step
- verify required secrets

Update only if necessary.

If no workflow exists:

- ask the user for deployment platform
- propose a minimal workflow
- create only after confirmation

---

## Rules

- Deploy only the app (`src/`, runtime dependencies, `LICENSE`); process files stay in the repository.

- Prefer **verifying existing workflows**.
- Do not overwrite workflows without confirmation.
- Never store secrets in the repository.

---

## Evidence to provide

- summary of what changed
- what was validated
- what remains out of scope
- recommended next slice

---

## Output

Deployment workflow verified or updated.

Record phase 5 and status in `docs/TASKS.md` per `AGENTS.md`.
