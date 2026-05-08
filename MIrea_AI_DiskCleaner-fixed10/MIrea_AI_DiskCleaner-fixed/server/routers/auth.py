"""Auth endpoints: POST /api/auth/register and POST /api/auth/login."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from config import RATE_LIMIT_LOGIN, RATE_LIMIT_REGISTER
from database.db import get_session
from models.schemas import AuthRequest, AuthResponse
from models.user import User
from rate_limit import limiter
from services.auth_service import (
    audit_logger,
    create_access_token,
    hash_password,
    verify_password_constant_time,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "-"


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(RATE_LIMIT_REGISTER)
async def register(
    request: Request,
    payload: AuthRequest,
    session: AsyncSession = Depends(get_session),
):
    ip = _client_ip(request)
    result = await session.execute(
        select(User).where(User.username == payload.username)
    )
    existing = result.scalar_one_or_none()
    if existing:
        audit_logger.info(
            "register_rejected username=%s ip=%s reason=duplicate",
            payload.username, ip,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        # The User model has exactly one UNIQUE constraint (username), so any
        # IntegrityError on insert is a duplicate. Match by SQLSTATE for
        # Postgres and by message for SQLite — neither database is wrong, the
        # drivers just expose the constraint differently.
        sqlstate = getattr(getattr(e, "orig", None), "sqlstate", None)
        msg = str(getattr(e, "orig", "")).lower()
        if sqlstate == "23505" or "unique constraint failed" in msg:
            audit_logger.info(
                "register_rejected username=%s ip=%s reason=duplicate_race",
                payload.username, ip,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already exists",
            )
        raise
    await session.refresh(user)

    token = create_access_token(user.id)
    audit_logger.info(
        "register_success user_id=%s username=%s ip=%s",
        user.id, user.username, ip,
    )

    return AuthResponse(
        user_id=user.id,
        username=user.username,
        access_token=token,
    )


@router.post("/login", response_model=AuthResponse)
@limiter.limit(RATE_LIMIT_LOGIN)
async def login(
    request: Request,
    payload: AuthRequest,
    session: AsyncSession = Depends(get_session),
):
    ip = _client_ip(request)
    result = await session.execute(
        select(User).where(User.username == payload.username)
    )
    user = result.scalar_one_or_none()

    # Always run bcrypt — even when the user doesn't exist — so an attacker
    # can't tell registered usernames apart by response timing.
    stored_hash = user.password_hash if user else None
    if not verify_password_constant_time(payload.password, stored_hash):
        audit_logger.info(
            "login_failed username=%s ip=%s reason=%s",
            payload.username, ip,
            "no_user" if user is None else "bad_password",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token = create_access_token(user.id)
    audit_logger.info(
        "login_success user_id=%s username=%s ip=%s",
        user.id, user.username, ip,
    )

    return AuthResponse(
        user_id=user.id,
        username=user.username,
        access_token=token,
    )
