from __future__ import annotations

import os

from itsdangerous import BadSignature, URLSafeSerializer
from passlib.context import CryptContext

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
SESSION_SALT = "session"

serializer = URLSafeSerializer(SECRET_KEY, salt=SESSION_SALT)
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
MAX_PASSWORD_LENGTH = 128


def hash_password(password: str) -> str:
    if len(password) > MAX_PASSWORD_LENGTH:
        raise ValueError("Password too long")
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    if len(password) > MAX_PASSWORD_LENGTH:
        return False
    return pwd_context.verify(password, password_hash)


def create_session(user_id: int) -> str:
    return serializer.dumps({"user_id": user_id})


def read_session(token: str) -> int | None:
    try:
        data = serializer.loads(token)
    except BadSignature:
        return None
    user_id = data.get("user_id")
    if not isinstance(user_id, int):
        return None
    return user_id
