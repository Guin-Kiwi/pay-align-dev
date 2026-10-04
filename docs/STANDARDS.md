# Standards

This project keeps its explicit core principles lightweight:

- AI-SDLC
- TDD
- Clean Architecture
- Small Vertical Slices

To strengthen practical quality and trustworthiness without turning the
template into a heavyweight process, the project also references two external
standards:

- **NIST SSDF**
- **OWASP ASVS**

These are used as guidance sources, not as a requirement to implement every
control in full for every student project.

---

## 1. NIST SSDF

**NIST Secure Software Development Framework (SSDF)** provides a practical
structure for integrating security into the software development lifecycle.

In this repository, SSDF mainly reinforces the idea that agentic work should:

- start from clearly defined tasks and responsibilities
- use repeatable, reviewable development practices
- include verification before claiming completion
- reduce the chance of unsafe or untraceable changes
- support secure change management and human oversight

### How to apply it here
Within this template, SSDF should be reflected in lightweight ways such as:

- clear task definitions
- explicit acceptance criteria
- validation before completion
- traceability from requirement to change
- human review for sensitive or risky steps
- secure handling of dependencies, secrets, and interfaces

### What it improves for agentic work
For AI-assisted work, SSDF helps prevent:
- vague task execution
- unverified completion claims
- insecure shortcuts
- undocumented assumptions
- weak review boundaries

---

## 2. OWASP ASVS

**OWASP Application Security Verification Standard (ASVS)** provides a
structured way to think about application security requirements and
verification.

In this repository, ASVS is not meant to be copied wholesale into every task.
Instead, it acts as a compact reminder that software slices should be checked
against basic security expectations, especially around:

- input validation
- authentication
- authorization
- session handling
- data protection
- error handling
- logging
- secure configuration

### How to apply it here
Within this template, ASVS should influence:

- acceptance criteria for use cases
- boundary checks in implementation
- test planning
- review prompts for security-sensitive changes

### What it improves for agentic work
For AI-assisted implementation, ASVS helps agents and reviewers avoid treating
“it works” as equivalent to “it is ready”. It encourages verification of
security-relevant behavior, especially at system boundaries.

---

## How these standards fit this repository

These standards are **secondary to repo-local instructions** for day-to-day
execution.

Priority order:

1. Repository task and project documents
2. Active use-case specification
3. This standards guidance
4. External references

That means:
- agents should not invent heavyweight compliance work
- agents should use these standards to improve quality of decisions, checks,
  and reviews
- humans remain responsible for deciding how much rigor is appropriate for the
  project stage

---

## Minimal practical checklist
When using this template, the standards above should usually translate into
questions like:

- Is the task clearly defined?
- Is the change small and reviewable?
- Are assumptions explicit?
- Is there evidence of validation?
- Are inputs and boundaries handled safely?
- Does anything security-sensitive require human review?
- Can a reviewer trace the change back to a requirement?

If the answer to several of these is “no”, the work is probably not ready to be
marked done.

---

## References
- NIST Secure Software Development Framework (SSDF): https://csrc.nist.gov/Projects/ssdf
- OWASP Application Security Verification Standard (ASVS): https://owasp.org/www-project-application-security-verification-standard/
