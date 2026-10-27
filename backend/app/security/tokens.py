from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from fastapi import HTTPException, status
from jwt.exceptions import InvalidTokenError

from app.config import settings


def create_access_token(user_id: UUID) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": now + timedelta(minutes=settings.access_token_ttl_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: UUID, token_id: UUID) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "jti": str(token_id),
        "type": "refresh",
        "iat": int(now.timestamp()),
        "exp": now + timedelta(days=settings.refresh_token_ttl_days),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _decode(token: str, expected_type: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except InvalidTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Could not validate credentials") from exc
    if payload.get("type") != expected_type or not payload.get("sub"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Could not validate credentials")
    return payload


def decode_access_token(token: str) -> UUID:
    payload = _decode(token, "access")
    try:
        return UUID(payload["sub"])
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Could not validate credentials") from exc


def decode_refresh_token(token: str) -> tuple[UUID, UUID]:
    payload = _decode(token, "refresh")
    try:
        return UUID(payload["sub"]), UUID(payload["jti"])
    except (KeyError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Could not validate credentials") from exc


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
