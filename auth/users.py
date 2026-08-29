import os

from dotenv import load_dotenv
from passlib.context import CryptContext

load_dotenv()

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ADMIN_PASSWORD_HASH = _pwd_context.hash(os.getenv("ADMIN_PASSWORD", "changeme"))

USERS: dict[str, str] = {
    "admin": ADMIN_PASSWORD_HASH,
}


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


def get_user_hash(username: str) -> str | None:
    return USERS.get(username)
