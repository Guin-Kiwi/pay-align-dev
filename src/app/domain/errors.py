# src/app/domain/errors.py


class AnnualLimitExceededError(Exception):
    """Raised when the annual gross wage limit is exceeded."""
    pass


class InvalidPayrollInputError(Exception):
    """Raised when payroll input values are invalid."""
    pass
