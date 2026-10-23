# ADR-006-uc-001-setup-api-and-wiring

## Status
Accepted (amended: see Amendment 1)

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
3. **Port.** `SetupRepository` in `src/app/application/ports/` has `get_employer()` and `save(employer, employee, employment)`. `save` stores all three atomically and links the employment to the employer and employee. Since [Amendment 1](#amendment-1-2026-10-23), it also has `get_employment(employment_id)`.
4. **Wiring.** `create_app()` in `src/app/infrastructure/web/app.py` builds the services and stores them on `app.state`. Routers read them through a small dependency such as `get_setup_service`. Tests call `create_app()` with a fake repository. The module-level `app = create_app()` stays, so the Docker start path keeps working.

Approved by Nano on 15 October 2026. The payroll router uses the same wiring pattern.

## Consequences
- Routers stay free of infrastructure imports. The payroll router adopted the same pattern, which cleared the architecture violation that the first payroll router caused.
- `create_app()` wires `SqlAlchemySetupRepository`, so setup data survives a restart. `InMemorySetupRepository` remains for tests.
- A JSON field that is missing entirely, or a wage with more than two decimals, returns FastAPI's 422. A blank value returns 400 from the domain.
- Follow-ups: `docs/PROJECT.md` does not list the endpoints yet; a human may add the input rules to the review-gated UC-001 spec; both routers now use the wiring pattern, so it can be proposed as a durable rule for `AGENTS.md`.

## Supersedes
none

## Amendment 1 (2026-10-23)

Decided on 23 October 2026: `SetupRepository` keeps `get_employment(employment_id)`, which returns the saved employment or `None`. Only tests use it, to check what setup saved; the application does not. Payroll reads the employment terms through its own port (`employment_terms`). Not chosen: removing it, which would change the port and its tests after the feature freeze without a gain for the user.
