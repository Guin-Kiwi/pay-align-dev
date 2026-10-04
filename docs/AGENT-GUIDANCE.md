# Agent Guidance

This document illustrates `AGENTS.md`'s Agent operating rules and Stop-and-ask
triggers with concrete heuristics and examples, and holds the standard task
response format. Read `AGENTS.md` first; load this file only when you need it.

---

## 1. Recognizing grounded work (illustrates "ground work in explicit requirements")

Good grounding signals:
- cites the active requirement
- references the current phase
- names the affected files or artifacts
- defines what success looks like

Weak grounding signals:
- generic best-practice output with no repo-local source
- large unsolicited rewrites
- implied requirements with no source
- claiming completion without validation

---

## 2. Sizing a step (illustrates "smallest useful slice")

Decompose further when:
- the task touches multiple files
- requirements are incomplete
- architecture could be affected
- implementation and validation are both needed

A good step is independently understandable, easy to review, easy to
validate, and easy to revert.

If the task can't be stated in one or two sentences, it isn't ready for
execution — narrow it first.

---

## 3. A reviewer's checklist (illustrates "optimize for reviewability")

A reviewer should be able to answer, from the output alone:
- what changed?
- why did it change?
- how was it validated?
- what remains unknown?

---

## 4. Use external guidance carefully
External guidance can improve results, but it should not override repo-local
intent.

Use external sources to support:
- task structuring
- prompt/instruction quality
- verification and review practices
- security considerations
- risk identification

Do not use external guidance to:
- expand scope without approval
- inject heavyweight process unnecessarily
- replace the repository’s defined operating model

---

## 5. Security-sensitive work deserves extra friction
For security-relevant work, agents should be more conservative, not less.

Apply extra care when changes affect:
- auth or authorization
- secrets or credentials
- trust boundaries
- external integrations
- data handling
- deployment or release behavior

In such cases, clearly flag the risk and prefer human confirmation before broad
changes.

---

## 6. Practical anti-patterns to avoid
Avoid these common failure modes:

- doing more than was asked
- silently broadening scope
- skipping validation
- presenting assumptions as facts
- rewriting large sections without necessity
- producing polished but ungrounded documentation
- using standards language without practical effect
- making risky decisions without escalation

---

## References
These sources informed the guidance in this file:

- Anthropic guidance on effective agent/task instruction, including clear
  success criteria and source-grounded work
- Microsoft guidance on system instructions, scoped behavior, boundaries,
  evaluation, and iteration
- Google guidance emphasizing decomposition and human-in-the-loop review for
  agentic systems
- NIST guidance as supporting context for trustworthy and governed
  software/AI development

See also:
- `docs/STANDARDS.md`

---

## Standard task response format
When performing a task, structure output using this shape when practical:

1. **Goal**
2. **Inputs consulted**
3. **Plan**
4. **Changes made**
5. **Validation**
6. **Assumptions / open questions**
7. **Next smallest step**

Keep responses concise, but include enough detail for a human reviewer to verify
the work.
