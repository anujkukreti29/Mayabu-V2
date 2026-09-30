"""Password hashing and policy for Mayabu accounts."""

from __future__ import annotations

import re

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=2,
    hash_len=32,
    salt_len=16,
)

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def is_valid_email(email: str) -> bool:
    value = normalize_email(email)
    return 3 <= len(value) <= 254 and bool(_EMAIL_RE.match(value))


def validate_password(password: str) -> str | None:
    """Return an error message, or None when the password is acceptable."""
    if password is None:
        return "Password is required."
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if len(password) > MAX_PASSWORD_LENGTH:
        return f"Password must be at most {MAX_PASSWORD_LENGTH} characters."
    return None


def hash_password(password: str) -> str:
    return _HASHER.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return bool(_HASHER.verify(password_hash, password))
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    try:
        return bool(_HASHER.check_needs_rehash(password_hash))
    except (InvalidHashError, VerificationError, TypeError, ValueError):
        return False
