# UC-001: Set Up an Employment

## 1. Intent
Enable a private household employer to initialize their system profile and register a new employee. This establishes the legal and financial baseline required to generate the AKBS registration payload and draft the standard hourly employment contract [cite: 4, 5].

## 2. Actors
- **Employer:** A private individual employing household help under the AKBS simplified procedure.

## 3. Inputs
- **Employer Data (if not yet initialized):** Full name, date of birth, home address, AKBS *Mitgliedernummer* (optional) [cite: 4].
- **Employee Data:** Full name, date of birth, home address, AHV number, cross-border work status (boolean) [cite: 4].
- **Employment Data:** Start date, regular weekly hours, holiday entitlement (in weeks), gross hourly wage, VAvplus accident insurance opt-in (boolean) [cite: 4, 7].

## 4. Main Success Scenario (Flow)
1. The employer opens the application and selects **"Set Up Employment"**. 
2. The system checks if an `Employer` record exists. If not, it prompts the employer to enter their details.
3. The employer enters the employee's details.
4. The employer enters the employment contract parameters.
5. The system validates the AHV number format and required fields.
6. The system saves the `Employer`, `Employee`, and `Employment` records to the database.
7. The system displays a **confirmation message** (e.g., "Employment set up successfully").

## 5. Acceptance Criteria
- The system must reject invalid AHV numbers (format: `756.XXXX.XXXX.XX`).
- The system must prevent duplicate `Employer` records.
- The system must save all data to the database.
- The system must display a confirmation message upon success.

## 6. Out of Scope
- **PDF generation**: Contracts and registration summaries will not be generated as PDFs.
- **Email notifications**: No emails will be sent to the employer or employee.
- **Pre-fill data**: The system will not pre-fill employer or employee details from external sources.
- **Legal compliance checks**: The system will not validate legal compliance beyond basic format checks (e.g., AHV number).
- **Cross-border employers**: The system will not handle additional requirements for cross-border employers.
- **Underage employees**: The system will not enforce additional requirements for employees under 18.

## 7. Future Considerations
- **PDF generation**: May be added in a future iteration for local file storage.
- **In-app notifications**: May be added to remind the employer of pending actions.
- **Pre-fill data**: May be added if integration with AKBS or other databases becomes available.

## 6. Test Intent (TDD)
- **Unit:** Validate AHV string formatting and validation logic.
- **Unit:** Ensure the `SetupService` throws an error if an `Employer` is created when one already exists.
- **Integration:** Verify that persisting an `Employment` correctly links to the respective `Employee` and `Employer` via foreign keys.