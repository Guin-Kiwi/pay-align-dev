import re
import secrets

from src.app.application.ports.account_repository import (
    AccountRepository,
    DuplicateAccountEmailError,
)
from src.app.application.ports.password_hasher import PasswordHasher
from src.app.domain.account import Account
from src.app.domain.constants import MIN_PASSWORD_LENGTH

EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class InvalidCredentialsError(Exception):
    pass


class AccountNotFoundError(Exception):
    pass


class AccountService:
    def __init__(self, repository: AccountRepository, password_hasher: PasswordHasher):
        self.repository = repository
        self.password_hasher = password_hasher
        self._dummy_hash = password_hasher.hash(secrets.token_urlsafe(32))

    def register(
        self, email: str, password: str, first_name: str, last_name: str
    ) -> Account:
        normalized_email = _normalize_email(email)
        if not first_name.strip() or not last_name.strip():
            raise ValueError("First and last name are required.")
        if (
            len(password) < MIN_PASSWORD_LENGTH
            or not any(character.isdecimal() for character in password)
            or not any(not character.isalnum() and not character.isspace() for character in password)
        ):
            raise ValueError(
                f"Password must contain at least {MIN_PASSWORD_LENGTH} characters, "
                "including a number and a special character."
            )
        if self.repository.get_by_email(normalized_email) is not None:
            raise DuplicateAccountEmailError
        account = Account(
            id=None,
            email=normalized_email,
            password_hash=self.password_hasher.hash(password),
            first_name=first_name.strip(),
            last_name=last_name.strip(),
        )
        return self.repository.add(account)

    def authenticate(self, email: str, password: str) -> Account:
        try:
            normalized_email = _normalize_email(email)
        except ValueError:
            normalized_email = ""
        account = self.repository.get_by_email(normalized_email) if normalized_email else None
        candidate_hash = account.password_hash if account is not None else self._dummy_hash
        verified = self.password_hasher.verify(password, candidate_hash)
        if account is None or not verified:
            raise InvalidCredentialsError
        return account

    def get(self, account_id: int) -> Account:
        account = self.repository.get_by_id(account_id)
        if account is None:
            raise AccountNotFoundError
        return account


def _normalize_email(email: str) -> str:
    normalized = email.strip().casefold()
    if not EMAIL_PATTERN.fullmatch(normalized):
        raise ValueError("A valid email address is required.")
    return normalized
