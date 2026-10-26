from sqlalchemy import Engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.app.application.ports.account_repository import (
    AccountRepository,
    DuplicateAccountEmailError,
)
from src.app.domain.account import Account
from src.app.infrastructure.orm_models import AccountRow


class SqlAlchemyAccountRepository(AccountRepository):
    def __init__(self, engine: Engine):
        self.engine = engine

    def get_by_email(self, email: str) -> Account | None:
        with Session(self.engine) as session:
            row = session.scalars(
                select(AccountRow).where(AccountRow.email == email)
            ).first()
            return _to_account(row) if row else None

    def get_by_id(self, account_id: int) -> Account | None:
        with Session(self.engine) as session:
            row = session.get(AccountRow, account_id)
            return _to_account(row) if row else None

    def add(self, account: Account) -> Account:
        try:
            with Session(self.engine) as session, session.begin():
                row = AccountRow(
                    email=account.email,
                    password_hash=account.password_hash,
                    first_name=account.first_name,
                    last_name=account.last_name,
                )
                session.add(row)
                session.flush()
                saved = _to_account(row)
        except IntegrityError as error:
            if self.get_by_email(account.email) is not None:
                raise DuplicateAccountEmailError from error
            raise
        return saved


def _to_account(row: AccountRow) -> Account:
    return Account(
        id=row.id,
        email=row.email,
        password_hash=row.password_hash,
        first_name=row.first_name,
        last_name=row.last_name,
    )
