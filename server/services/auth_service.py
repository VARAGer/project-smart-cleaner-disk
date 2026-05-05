"""Password hashing, JWT issuance/verification, and the audit logger."""

import logging
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from config import BCRYPT_ROUNDS, JWT_ALGORITHM, JWT_EXPIRATION_MINUTES, JWT_SECRET

# Bumped above the passlib default of 12 to slow down offline cracking if the
# database leaks. Combine with rate limiting on /login (in routers/auth.py).
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=BCRYPT_ROUNDS,
)

# Pre-computed hash of an unguessable string. Used by the login flow to spend
# the same CPU time on a missing-user lookup as on an existing one, so an
# attacker can't tell registered usernames apart by response timing.
_DUMMY_HASH = pwd_context.hash("dummy-for-constant-time-login-do-not-use")


# Dedicated logger for security events (login, register, token rejections).
# Configured at app startup; emits to stdout by default so `docker logs` shows
# the trail without any external collector.
audit_logger = logging.getLogger("audit")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def verify_password_constant_time(plain_password: str, hashed_password: str | None) -> bool:
    """
    Verify a password while spending bcrypt time even if `hashed_password` is
    None. Returns False in that case but still pays the CPU cost, neutralising
    user-enumeration via response timing.
    """
    if hashed_password is None:
        pwd_context.verify(plain_password, _DUMMY_HASH)
        return False
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=JWT_EXPIRATION_MINUTES
    )
    payload = {
        "sub": user_id,
        "exp": expire,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None
