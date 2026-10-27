from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.entities import ProfileTerm, RefreshSession, ResearchProfile, User
from app.models.enums import ProfileTermKind
from app.schemas.dto import ProfileUpdate, RegisterIn, UserUpdate
from app.security.passwords import DUMMY_HASH, password_hash
from app.security.tokens import create_access_token, create_refresh_token, decode_refresh_token, hash_token
from app.services.support import index_profile, load_terms, profile_document, serialize_user


async def register_user(session: AsyncSession, payload: RegisterIn) -> User:
    email = payload.email.lower()
    existing = await session.scalar(select(User).where(User.email == email))
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    user = User(name=payload.name.strip(), email=email, password_hash=password_hash.hash(payload.password))
    session.add(user)
    await session.flush()
    session.add(ResearchProfile(user_id=user.id))
    await session.flush()
    return user


async def authenticate(session: AsyncSession, email: str, password: str) -> User:
    user = await session.scalar(select(User).where(User.email == email.lower()))
    if user is None:
        password_hash.verify(password, DUMMY_HASH)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    if not password_hash.verify(password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    return user


async def issue_tokens(session: AsyncSession, user: User) -> tuple[str, str]:
    access = create_access_token(user.id)
    refresh = create_refresh_token(user.id, uuid4())
    session.add(
        RefreshSession(
            user_id=user.id,
            token_hash=hash_token(refresh),
            expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_ttl_days),
        )
    )
    return access, refresh


async def rotate_tokens(session: AsyncSession, raw_token: str) -> tuple[User, str, str]:
    user_id, _token_id = decode_refresh_token(raw_token)
    row = await session.scalar(select(RefreshSession).where(RefreshSession.token_hash == hash_token(raw_token)))
    if row is None or row.user_id != user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Could not validate credentials")
    now = datetime.now(UTC)
    if row.revoked_at is not None:
        await session.execute(
            update(RefreshSession)
            .where(RefreshSession.user_id == user_id, RefreshSession.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Could not validate credentials")
    if row.expires_at < now:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Could not validate credentials")
    row.revoked_at = now
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Could not validate credentials")
    access, refresh = await issue_tokens(session, user)
    return user, access, refresh


async def revoke_token(session: AsyncSession, raw_token: str | None) -> None:
    if not raw_token:
        return
    try:
        decode_refresh_token(raw_token)
    except HTTPException:
        return
    row = await session.scalar(select(RefreshSession).where(RefreshSession.token_hash == hash_token(raw_token)))
    if row and row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)


async def update_user(session: AsyncSession, user: User, payload: UserUpdate) -> User:
    if "name" in payload.model_fields_set and payload.name is not None:
        user.name = payload.name.strip()
    if "bio" in payload.model_fields_set:
        user.bio = payload.bio.strip() if payload.bio else None
    if "research_level" in payload.model_fields_set:
        user.research_level = payload.research_level
    terms = await load_terms(session, user.id)
    await index_profile(session, user.id, profile_document(user, terms))
    return user


async def replace_profile(session: AsyncSession, user: User, payload: ProfileUpdate) -> list[ProfileTerm]:
    profile = await session.scalar(select(ResearchProfile).where(ResearchProfile.user_id == user.id))
    if profile is None:
        profile = ResearchProfile(user_id=user.id)
        session.add(profile)
        await session.flush()
    await session.execute(delete(ProfileTerm).where(ProfileTerm.profile_id == profile.id))
    groups = (
        (ProfileTermKind.interest, payload.research_interests),
        (ProfileTermKind.skill, payload.skills),
        (ProfileTermKind.topic, payload.preferred_topics),
    )
    for kind, labels in groups:
        seen: set[str] = set()
        for label in labels:
            cleaned = label.strip()
            if not cleaned:
                continue
            key = cleaned.casefold()
            if key in seen:
                continue
            seen.add(key)
            if len(cleaned) > 200:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A profile term is too long")
            session.add(ProfileTerm(profile_id=profile.id, kind=kind, label=cleaned))
    await session.flush()
    terms = await load_terms(session, user.id)
    await index_profile(session, user.id, profile_document(user, terms))
    return terms


async def current_user_out(session: AsyncSession, user: User):
    return serialize_user(user, await load_terms(session, user.id))
