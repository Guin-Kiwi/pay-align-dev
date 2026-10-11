from dataclasses import dataclass
from datetime import date, time


@dataclass(frozen=True)
class WorkEntry:
    """One day's work details used to calculate monthly paid hours."""

    work_date: date
    start_time: time
    end_time: time
    unpaid_break_hours: float = 0.0
    paid: bool = True

    def __post_init__(self) -> None:
        if self.end_time <= self.start_time:
            raise ValueError("End time must be after start time.")
        if self.unpaid_break_hours < 0:
            raise ValueError("Unpaid break hours cannot be negative.")
