# src/app/domain/errors.py


class AnnualLimitExceededError(Exception):
    """Raised when the annual gross wage limit is exceeded."""
    pass


class InvalidPayrollInputError(Exception):
    """Raised when payroll input values are invalid."""
    pass


class DuplicateMonthError(Exception):
    """Raised when an employment already has payroll for a month."""
    pass


class InvalidHolidayBalanceError(Exception):
    """Raised when a payroll snapshot contains an invalid balance."""
    pass
