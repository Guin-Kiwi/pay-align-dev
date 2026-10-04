# UC-001: Set Up an Employment

## Goal
Enable a private household employer to initialize their system profile and register a new employee. This establishes the legal and financial baseline required for payroll processing.

## Business value
This use case simplifies the onboarding process for private household employers in Basel-Stadt, ensuring compliance with AKBS requirements and reducing administrative burden.

## Scope

### In scope
- Initializing an `Employer` record if none exists.
- Registering an `Employee` and `Employment` with required details.
- Validating AHV numbers and required fields.
- Saving all data to the database.

### Out of scope
- PDF generation for contracts or registration summaries.
- Email notifications to the employer or employee.
- Pre-filling employer or employee details from external sources.
- Legal compliance checks beyond basic format validation (e.g., AHV number).
- Support for cross-border employers or underage employees.

## Actors

**Primary**: Employer (a private individual employing household help under the AKBS simplified procedure).

**Secondary**: None.

## Preconditions
- The employer has access to the PayAlign application.
- The employer has the required details for themselves, the employee, and the employment contract.

## Trigger
The employer selects **"Set Up Employment"** in the application.

## Main flow

1. The employer opens the application and selects **"Set Up Employment"**. 
2. The system checks if an `Employer` record exists. If not, it prompts the employer to enter their details.
3. The employer enters the employee's details.
4. The employer enters the employment contract parameters.
5. The system validates the AHV number format and required fields.
6. The system saves the `Employer`, `Employee`, and `Employment` records to the database.
7. The system displays a **confirmation message** (e.g., "Employment set up successfully").

## Alternate / edge flows
- If the AHV number is invalid, the system displays an example (e.g., `756.XXXX.XXXX.XX`) and prompts the employer to retry.

## Errors / failure cases
- Invalid AHV number format.
- Missing required fields (e.g., employee address).
- Duplicate `Employer` record.

## Acceptance criteria
- The system must reject invalid AHV numbers (format: `756.XXXX.XXXX.XX`).
- The system must prevent duplicate `Employer` records.
- The system must save all data to the database.
- The system must display a confirmation message upon success.

## Security / trust-boundary notes
- All data is stored locally and not shared with external systems.
- The employer must authenticate to access the system (future consideration).

## Validation plan
- **Unit Tests**: Validate AHV string formatting and validation logic.
- **Unit Tests**: Ensure the `SetupService` throws an error if an `Employer` is created when one already exists.
- **Integration Tests**: Verify that persisting an `Employment` correctly links to the respective `Employee` and `Employer` via foreign keys.

## Open questions / assumptions
- Assumption: The employer has all required details (e.g., AHV number) at hand.
- Open question: Should the system support bulk import of employees in the future?

## Notes for implementation
- Use the `SetupService` to handle the onboarding logic.
- Ensure all validations are performed before saving to the database.