from abc import ABC, abstractmethod


class PasswordHasher(ABC):
    @abstractmethod
    def hash(self, password: str) -> str:
        """Return an adaptive one-way password hash."""

    @abstractmethod
    def verify(self, password: str, password_hash: str) -> bool:
        """Return whether the password matches the stored hash."""
