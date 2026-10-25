import pytest

from src.app.application.account_service import (
    AccountService,
    DuplicateAccountEmailError,
    InvalidCredentialsError,
)
from src.app.application.ports.account_repository import AccountRepository
from src.app.application.ports.password_hasher import PasswordHasher


class FakeAccountRepository(AccountRepository):
    def __init__(self):
        self.accounts = {}
        self.next_id = 1

    def get_by_email(self, email):
        return self.accounts.get(email)

    def get_by_id(self, account_id):
        return next(
            (account for account in self.accounts.values() if account.id == account_id),
            None,
        )

    def add(self, account):
        if account.email in self.accounts:
            raise DuplicateAccountEmailError
        saved = type(account)(
            self.next_id,
            account.email,
            account.password_hash,
            account.first_name,
            account.last_name,
        )
        self.next_id += 1
        self.accounts[saved.email] = saved
        return saved


class FakePasswordHasher(PasswordHasher):
    def hash(self, password):
        return f"hashed:{password}"

    def verify(self, password, password_hash):
        return password_hash == f"hashed:{password}"


def test_registration_normalizes_email_and_never_persists_plain_password():
    repository = FakeAccountRepository()
    service = AccountService(repository, FakePasswordHasher())

    account = service.register(
        " Anna@Example.CH ", "Secret1!", " Anna ", " Muster "
    )

    assert account.email == "anna@example.ch"
    assert account.first_name == "Anna"
    assert account.last_name == "Muster"
    assert account.password_hash == "hashed:Secret1!"
    assert repository.accounts[account.email].password_hash != "Secret1!"


def test_registration_rejects_duplicate_normalized_email():
    service = AccountService(FakeAccountRepository(), FakePasswordHasher())
    service.register("anna@example.ch", "Secret1!", "Anna", "Muster")

    with pytest.raises(DuplicateAccountEmailError):
        service.register(" ANNA@example.ch ", "Different1!", "A", "B")


def test_authentication_uses_the_same_error_for_unknown_email_and_wrong_password():
    service = AccountService(FakeAccountRepository(), FakePasswordHasher())
    service.register("anna@example.ch", "Secret1!", "Anna", "Muster")

    with pytest.raises(InvalidCredentialsError):
        service.authenticate("anna@example.ch", "wrong")
    with pytest.raises(InvalidCredentialsError):
        service.authenticate("unknown@example.ch", "wrong")


@pytest.mark.parametrize("password", ["", "Abc1!xy", "abcdefgh!", "abcdefg1", "abcdef1 "])
def test_registration_checks_password_policy_before_hashing_or_saving(password):
    repository = FakeAccountRepository()
    service = AccountService(repository, FakePasswordHasher())
    with pytest.raises(ValueError, match="Password must"):
        service.register("anna@example.ch", password, "Anna", "Muster")
    assert repository.accounts == {}


@pytest.mark.parametrize("password", ["Secret1!", "A longer passphrase with 1 symbol!", "éclair1☃", "a" * 64 + "1!"])
def test_password_policy_allows_long_passwords_and_preserves_them(password):
    service = AccountService(FakeAccountRepository(), FakePasswordHasher())
    service.register("anna@example.ch", password, "Anna", "Muster")
    assert service.authenticate("anna@example.ch", password).email == "anna@example.ch"
