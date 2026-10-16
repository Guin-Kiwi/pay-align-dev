# ADR-006-uc-001-setup-api-and-wiring

## Status
Accepted

## Context
UC-001 saves an employer, an employee and an employment. It rejects invalid AHV numbers and missing fields, prevents a second employer, confirms success, and validates everything before saving. The UI needs a stable endpoint list. [ADR-001](ADR-001-clean-architecture-boundaries.md) forbids the interfaces layer from importing infrastructure, but the first payroll router builds its own repository, which the stricter architecture test reports.

## Alternatives
- One endpoint per entity (employer, employee, employment): not chosen, because a failure in a later call leaves the earlier records saved.
- One repository port per entity plus a unit of work: not chosen, because it adds classes to write, fake and copy without a current need.
- Wiring through `app.dependency_overrides`: not chosen, because FastAPI documents that feature for tests.
- Accepting AHV numbers without dots and storing them with dots: not chosen; the UC-001 spec states the dotted format, and the strict check is simpler.
- Requiring only name and address: not chosen, because every employer and employee column in the planned tables is `NOT NULL`.

## Decision
1. **Endpoints.** `GET /api/v1/employer` returns the one employer, or 404 before setup. `POST /api/v1/setup` takes `employer` (only when none exists), `employee` and `employment`, validates all three, then saves them in one transaction. It answers 201 with "Employment set up successfully" and the three ids, 400 for invalid input with the failing part named (for example `Employee: Address is required.`), and 409 when an employer is sent although one exists. `POST /api/v1/employments` is removed.
2. **Input rules.** AHV numbers must match `756.XXXX.XXXX.XX` exactly. Employer name, address, AHV number and contact info, and employee name, address, AHV number and nationality are required. Blank or spaces-only values count as missing.
3. **Port.** `SetupRepository` in `src/app/application/ports/` has `get_employer()` and `save(employer, employee, employment)`. `save` stores all three atomically and links the employment to the employer and employee.
4. **Wiring.** `create_app()` in `src/app/infrastructure/web/app.py` builds the services and stores them on `app.state`. Routers read them through a small dependency such as `get_setup_service`. Tests call `create_app()` with a fake repository. The module-level `app = create_app()` stays, so the Docker start path keeps working.

Approved by Nano on 15 October 2026. The wiring pattern applies to the payroll router once Ayla confirms it.

## Consequences
- Routers stay free of infrastructure imports. The payroll router can adopt the same pattern to clear the remaining architecture violation.
- Until the SQLAlchemy setup repository exists, the app uses an in-memory setup repository and forgets setup data on restart.
- A JSON field that is missing entirely returns FastAPI's 422. A blank value returns 400 from the domain.
- Follow-ups: add the endpoint list to `docs/PROJECT.md` after PR #9 merges; a human may add the input rules to the review-gated UC-001 spec; once both routers use the wiring pattern, propose it as a durable rule for `AGENTS.md`.

## Supersedes
none
