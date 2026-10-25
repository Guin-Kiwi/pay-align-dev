from pwdlib import PasswordHash

from src.app.application.ports.password_hasher import PasswordHasher


class PwdlibPasswordHasher(PasswordHasher):
    def __init__(self):
        self._password_hash = PasswordHash.recommended()

    def hash(self, password: str) -> str:
        return self._password_hash.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        return self._password_hash.verify(password, password_hash)
