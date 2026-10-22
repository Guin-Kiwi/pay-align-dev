from dataclasses import dataclass
from datetime import date, time
from typing import Iterable, Optional

from src.app.domain.errors import InvalidPayrollInputError
from src.app.domain.hour_categories import HourCategory


def calculate_paid_minutes(start_time: time, end_time: time, unpaid_break_minutes: int) -> int:
    """Return paid whole minutes for one day after unpaid breaks."""
    if end_time <= start_time:
        raise InvalidPayrollInputError("End time must be after start time.")
    if isinstance(unpaid_break_minutes, bool) or not isinstance(unpaid_break_minutes, int):
        raise InvalidPayrollInputError("Unpaid break minutes must be a whole number.")
    if unpaid_break_minutes < 0:
        raise InvalidPayrollInputError("Unpaid break minutes cannot be negative.")

    elapsed = (
        end_time.hour * 60 + end_time.minute
        - start_time.hour * 60 - start_time.minute
    )
    paid_minutes = elapsed - unpaid_break_minutes
    if paid_minutes < 0:
        raise InvalidPayrollInputError("Unpaid breaks exceed the work duration.")
    return paid_minutes


@dataclass(frozen=True)
class WorkEntry:
    """One daily entry, classified into an hour category.

    With a start and an end time, the paid minutes are the time between them
    less the unpaid break (UC-002). Entries without times carry minutes only.
    """

    work_date: date
    category: HourCategory
    paid_minutes: int
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    unpaid_break_minutes: int = 0

    def __post_init__(self) -> None:
        if isinstance(self.paid_minutes, bool) or not isinstance(self.paid_minutes, int):
            raise InvalidPayrollInputError("Paid minutes must be a whole number.")
        if self.paid_minutes < 0:
            raise InvalidPayrollInputError("Paid minutes cannot be negative.")
        object.__setattr__(self, "category", HourCategory(self.category))
        if (self.start_time is None) != (self.end_time is None):
            raise InvalidPayrollInputError("An entry needs both a start and an end time.")
        if self.start_time is None:
            return
        derived = calculate_paid_minutes(
            self.start_time, self.end_time, self.unpaid_break_minutes
        )
        if derived != self.paid_minutes:
            raise InvalidPayrollInputError(
                "Paid minutes do not match the start time, end time and break."
            )

    @classmethod
    def from_times(
        cls,
        work_date: date,
        category: HourCategory,
        start_time: time,
        end_time: time,
        unpaid_break_minutes: int = 0,
    ) -> "WorkEntry":
        return cls(
            work_date=work_date,
            category=category,
            paid_minutes=calculate_paid_minutes(start_time, end_time, unpaid_break_minutes),
            start_time=start_time,
            end_time=end_time,
            unpaid_break_minutes=unpaid_break_minutes,
        )


def reject_overlapping_entries(entries: Iterable[WorkEntry]) -> None:
    """Reject two timed entries of one day whose time spans overlap."""
    by_day: dict[date, list[WorkEntry]] = {}
    for entry in entries:
        if entry.start_time is not None:
            by_day.setdefault(entry.work_date, []).append(entry)
    for day_entries in by_day.values():
        day_entries.sort(key=lambda entry: entry.start_time)
        for earlier, later in zip(day_entries, day_entries[1:]):
            if later.start_time < earlier.end_time:
                raise InvalidPayrollInputError(
                    f"Work entries overlap on {earlier.work_date.isoformat()}."
                )
