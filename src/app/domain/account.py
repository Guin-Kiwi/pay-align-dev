from dataclasses import dataclass


@dataclass(frozen=True)
class Account:
    id: int | None
    email: str
    password_hash: str
    first_name: str
    last_name: str
