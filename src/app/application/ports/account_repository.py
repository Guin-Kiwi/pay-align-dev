from abc import ABC, abstractmethod

from src.app.domain.account import Account


class DuplicateAccountEmailError(Exception):
    """Raised when another account already uses this normalized email."""


class AccountRepository(ABC):
    @abstractmethod
    def get_by_email(self, email: str) -> Account | None:
        """Return an account by its normalized email address."""

    @abstractmethod
    def get_by_id(self, account_id: int) -> Account | None:
        """Return an account by its database-generated ID."""

    @abstractmethod
    def add(self, account: Account) -> Account:
        """Persist an account, rejecting a duplicate normalized email."""
