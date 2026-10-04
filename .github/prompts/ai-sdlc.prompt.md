---
mode: agent
description: Start or continue an AI-SDLC phase in this repository.
---

Follow `AGENTS.md`. Read `docs/INDEX.json`, then `docs/TASKS.md` and `docs/PROJECT.md`.

Phase: ${input:phase:bootstrap | specify | design | develop | validate | deploy}
Request: ${input:request:What should this phase deliver?}

Open the matching skill, `skills/ai-sdlc-<N>-<phase>/SKILL.md`, and follow it.
Set `docs/TASKS.md` to that phase with status in-progress. If the skill's
required input is missing, ask me before doing anything else.
