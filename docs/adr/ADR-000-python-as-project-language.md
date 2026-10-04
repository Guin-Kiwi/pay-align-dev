# ADR-000-python-as-project-language

## Status
Accepted

## Context
The template was written to avoid assuming a language, but it already ships a
Python devcontainer profile, `environments/python/` and `scripts/setup-python.sh`.
Its guidance said "no assumed language" while its tooling assumed Python, and
supporting other languages would mean maintaining equivalent environments,
scripts and guidance for each. The template's intended use is the creator's
project work across many courses, all of which use Python.

## Alternatives
- Stay language-agnostic: rejected. It would require generic tooling for
  stacks nobody is using, and the repo already behaves as Python-first.
- Support several named stacks: rejected as out of scope for the template's
  current use.

## Decision
The template assumes Python for derived projects. The lifecycle method stays
stack-neutral in wording, but the supported environment, scripts and
BOOTSTRAP flow are Python. Frameworks (the default profile uses FastAPI) and
deployment platforms are still chosen per project during BOOTSTRAP.
Approved by the template creator, 2026-10-01.

## Consequences
- Easier: BOOTSTRAP no longer asks for a language or runtime, and guidance no
  longer carries "replace the profile for another stack" branches.
- Harder: a non-Python project is outside the template's scope; it needs a new
  ADR superseding this one and the matching environment and script changes.
- Lifecycle scripts remain bash glue; rewriting them in Python is a separate
  slice and is not decided here.
- `AGENTS.md`, `skills/ai-sdlc-0-bootstrap/` and `README.md` are updated to
  match.

## Supersedes
none
