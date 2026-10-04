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
1. System checks if an `Employer` record exists. If not, prompts for and persists the `Employer` initialization data.
2. User enters the `Employee` demographic and identification data.
3. User enters the `Employment` contract parameters.
4. System validates the AHV number format and required fields.
5. System persists the `Employee` and `Employment` entities, linking them to the `Employer`.
6. System outputs a structured AKBS registration summary and the baseline contract parameters.

## 5. Acceptance Criteria
- **Singleton Employer:** The system must restrict the creation of an `Employer` record if one already exists in the database.
- **AHV Validation:** The system must enforce the 13-digit AHV number format (`756.XXXX.XXXX.XX`) for the employee [cite: 4].
- **Completeness:** The system must reject the setup if the employee's home address is missing, as it is required for simplified procedure tax settlement [cite: 4].
- **Output Payload:** The system must successfully assemble a data object containing all fields requested by the AKBS online registration form [cite: 4].

## 6. Test Intent (TDD)
- **Unit:** Validate AHV string formatting and validation logic.
- **Unit:** Ensure the `SetupService` throws an error if an `Employer` is created when one already exists.
- **Integration:** Verify that persisting an `Employment` correctly links to the respective `Employee` and `Employer` via foreign keys.