import os

import bcrypt
from dotenv import load_dotenv

load_dotenv()

_raw = os.getenv("ADMIN_PASSWORD", "changeme").encode()
ADMIN_PASSWORD_HASH: bytes = bcrypt.hashpw(_raw, bcrypt.gensalt())

USERS: dict[str, bytes] = {
    "admin": ADMIN_PASSWORD_HASH,
}


def verify_password(plain: str, hashed: bytes) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed)


def get_user_hash(username: str) -> bytes | None:
    return USERS.get(username)
