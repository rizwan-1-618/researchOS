from __future__ import annotations

import asyncio
from uuid import UUID

import httpx
from contextlib import asynccontextmanager

from app.config import settings
from app.db import new_engine, session_factory
from app.services.citations import expand_citations
from app.services.processing import fetch_remote_pdf, process_stored_pdf


@asynccontextmanager
async def worker_session():
    engine = new_engine()
    factory = session_factory(engine)
    try:
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    finally:
        await engine.dispose()


def process_pdf(paper_id: str, apply_metadata: bool) -> None:
    asyncio.run(_process_pdf(paper_id, apply_metadata))


def expand_paper_citations(paper_id: str, user_id: str) -> None:
    asyncio.run(_expand(paper_id, user_id))


def fetch_pdf(paper_id: str, user_id: str) -> None:
    asyncio.run(_fetch(paper_id, user_id))


async def _process_pdf(paper_id: str, apply_metadata: bool) -> None:
    async with worker_session() as session:
        await process_stored_pdf(session, UUID(paper_id), apply_metadata)


async def _expand(paper_id: str, user_id: str) -> None:
    async with worker_session() as session:
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as http:
            await expand_citations(session, http, UUID(paper_id), UUID(user_id))


async def _fetch(paper_id: str, user_id: str) -> None:
    async with worker_session() as session:
        await fetch_remote_pdf(session, UUID(paper_id), UUID(user_id))
