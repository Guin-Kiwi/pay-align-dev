# Skill Design Sources (Future Reference)

Status: roadmap note, not an accepted architecture decision. No ADR yet.
Nothing here changes current runtime behaviour, dependencies, or CI.

## Purpose

Capture candidate standards and specifications that could inform future skill
and contract design, so the comparison work is not lost, without adopting any
of it prematurely.

## Source Comparison Matrix

| Source | Domain | Relevance to skills | Maturity |
|---|---|---|---|
| MCP (Model Context Protocol) | Tool/context interop | Direct: skill-tool contract shape | Stable, active |
| JSON Schema | Data validation | Direct: input/output contract validation | Stable |
| W3C PROV | Provenance | Direct: tracing skill execution lineage | Stable (W3C Rec) |
| OpenAPI | HTTP API description | Conditional: if a skill wraps an HTTP API | Stable |
| AsyncAPI | Async/event API description | Conditional: if a skill wraps an event bus | Stable |
| OpenTelemetry | Observability | Conditional: skill execution tracing/metrics | Stable, active |
| OCI (Open Container Initiative) | Packaging/distribution | Conditional: if skills are containerized | Stable |
| SPDX / CycloneDX | SBOM / dependency manifest | Conditional: if skill dependencies need an SBOM | Stable |
| SLSA | Supply-chain integrity levels | Conditional: if skills are released as artefacts | Stable |
| Sigstore | Artifact signing | Conditional: paired with SLSA for signed releases | Stable, active |
| CUE | Config/schema language | Conditional: alternative to JSON Schema for contracts | Stable, niche |
| OPA / Rego | Policy enforcement | Conditional: if skill execution needs policy gates | Stable |
| A2A (Agent2Agent) | Agent-to-agent interop | Conditional: multi-agent skill handoff | Emerging |
| Agent Protocol | Agent task lifecycle | Conditional: alternative agent lifecycle contract | Emerging |

## Tier Prioritization

- **Tier 1 (recommended foundation):** MCP, JSON Schema, W3C PROV — cover
  tool/context interop, contract validation, and execution provenance, the
  three concerns every skill already has today.
- **Tier 2 (conditional, infra-triggered):** OpenAPI, AsyncAPI,
  OpenTelemetry — adopt only when a skill actually wraps an HTTP API, an
  event-driven API, or needs tracing/metrics beyond logs.
- **Tier 3 (conditional, supply-chain-triggered):** OCI, SPDX/CycloneDX,
  SLSA, Sigstore — adopt only once skills are packaged and released as
  distributable artefacts.
- **Tier 4 (conditional, interop/policy-triggered):** CUE, OPA/Rego, A2A,
  Agent Protocol — adopt only if a concrete need for policy-as-code or
  cross-agent interop emerges.

## Recommended Foundation

- **MCP** — shape of the skill/tool contract (inputs, outputs, capabilities).
- **JSON Schema** — validation for skill inputs/outputs and metadata.
- **W3C PROV** — lineage of what produced a skill's output, for audit and
  debugging.

## Proposed Skill Metadata and Contract Fields

- `name`, `description` — identity and discovery (already in use).
- `inputs` / `outputs` — JSON Schema definitions.
- `provenance` — W3C PROV-compatible record of invocation (who/what/when).
- `capabilities` — declared side effects (read-only, network, filesystem).
- `version` — semantic version of the skill contract itself.

## Criteria for Creating a Reusable Skill

- The task recurs across at least two use cases or phases.
- The steps are stable enough to encode without per-use-case rewriting.
- The input/output contract can be expressed without an escape hatch.
- Reuse would remove meaningful duplication, not just save typing once.

## Deferred / Not Yet Adopted

- OpenAPI, AsyncAPI, OpenTelemetry, OCI, SPDX/CycloneDX, SLSA, Sigstore, CUE,
  OPA/Rego, A2A, Agent Protocol — tracked above as conditional, none adopted.
- No runtime, dependency, CI, or release changes are implied by this note.
- Revisit this note once a concrete skill needs one of the conditional
  standards; promote the relevant section to an ADR at that point.
