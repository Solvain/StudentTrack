import os
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

ALGORITHM = "HS256"
password_hasher = PasswordHash.recommended()


def secret_key() -> str:
    key = os.environ.get("JWT_SECRET_KEY", "")
    if len(key.encode()) < 32:
        raise RuntimeError("JWT_SECRET_KEY must contain at least 32 bytes")
    return key


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, encoded: str | None) -> bool:
    return password_hasher.verify(password, encoded) if encoded else False


def create_access_token(student_id: int) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": str(student_id), "iat": now, "exp": now + timedelta(minutes=30)},
        secret_key(), algorithm=ALGORITHM,
    )


def decode_student_id(token: str) -> int:
    payload = jwt.decode(token, secret_key(), algorithms=[ALGORITHM],
                         options={"require": ["sub", "exp", "iat"]})
    student_id = int(payload["sub"])
    if not 0 < student_id <= 2**31 - 1:
        raise ValueError("Invalid student ID")
    return student_id
