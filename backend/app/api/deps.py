from __future__ import annotations

from fastapi import HTTPException, Query, Request, status
from fastapi.security import OAuth2PasswordBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.entities import User
from app.security.tokens import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)


class PageParams:
    def __init__(self, limit: int, offset: int):
        self.limit = limit
        self.offset = offset


async def get_session(request: Request):
    factory = request.app.state.session_factory
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_user(request: Request, session: AsyncSession) -> User:
    token = None
    header = request.headers.get("authorization")
    if header and header.lower().startswith("bearer "):
        token = header.split(" ", 1)[1].strip()
    if not token:
        token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Could not validate credentials")
    user_id = decode_access_token(token)
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Could not validate credentials")
    return user


def get_http(request: Request):
    return request.app.state.http


def get_redis(request: Request) -> Redis:
    return request.app.state.redis


def pagination(
    limit: int | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
) -> PageParams:
    resolved = settings.api_default_page_size if limit is None else limit
    if resolved < 1 or resolved > settings.api_max_page_size:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid page size")
    return PageParams(resolved, offset)


async def enforce_auth_rate(request: Request) -> None:
    redis = request.app.state.redis
    host = request.client.host if request.client else "unknown"
    if settings.trust_proxy:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            host = forwarded.split(",", 1)[0].strip()
    key = f"auth-rate:{host}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, settings.auth_rate_window_seconds)
    if count > settings.auth_rate_limit:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts")


def set_auth_cookies(response, access: str, refresh: str) -> None:
    response.set_cookie(
        "access_token",
        access,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.access_token_ttl_minutes * 60,
        path="/",
    )
    response.set_cookie(
        "refresh_token",
        refresh,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.refresh_token_ttl_days * 86400,
        path="/api/auth",
    )


def clear_auth_cookies(response) -> None:
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/api/auth")
