from __future__ import annotations

import asyncio
import io
import logging
from uuid import UUID, uuid4

from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.chunking import chunk_pages
from app.integrations.pdf_fetch import download_public_pdf
from app.integrations.types import ExternalAuthor
from app.models.entities import Paper, PaperFile
from app.models.enums import ProcessingStatus
from app.services.catalog import set_authors
from app.services.support import index_paper, replace_chunks
from app.storage.files import get_storage

logger = logging.getLogger(__name__)


def extract_pdf(data: bytes) -> tuple[dict[str, str], list[tuple[int, str]]]:
    reader = PdfReader(io.BytesIO(data))
    metadata: dict[str, str] = {}
    if reader.metadata:
        title = reader.metadata.title
        author = reader.metadata.author
        if isinstance(title, str) and title.strip():
            metadata["title"] = title.strip()
        if isinstance(author, str) and author.strip():
            metadata["author"] = author.strip()
    pages: list[tuple[int, str]] = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            logger.exception("page text extraction failed")
            text = ""
        pages.append((index, text))
    return metadata, pages


async def process_stored_pdf(session: AsyncSession, paper_id: UUID, apply_metadata: bool) -> None:
    file_row = await session.scalar(select(PaperFile).where(PaperFile.paper_id == paper_id))
    paper = await session.get(Paper, paper_id)
    if file_row is None or paper is None:
        return
    file_row.processing_status = ProcessingStatus.processing
    file_row.processing_error = None
    await session.flush()
    try:
        data = await get_storage().get(file_row.storage_key)
        metadata, pages = await asyncio.to_thread(extract_pdf, data)
        if apply_metadata and metadata.get("title"):
            paper.title = metadata["title"]
        from app.services.catalog import authorships_for

        if metadata.get("author") and not await authorships_for(session, paper.id):
            await set_authors(session, paper, [ExternalAuthor(name=metadata["author"])], replace=False)
        await replace_chunks(session, paper.id, chunk_pages(pages))
        await index_paper(session, paper)
        file_row.processing_status = ProcessingStatus.ready
    except Exception:
        logger.exception("pdf processing failed")
        file_row.processing_status = ProcessingStatus.failed
        file_row.processing_error = "The PDF could not be processed"


async def store_pdf(
    session: AsyncSession,
    *,
    paper_id: UUID,
    user_id: UUID,
    file_name: str,
    data: bytes,
) -> PaperFile:
    existing = await session.scalar(select(PaperFile).where(PaperFile.paper_id == paper_id))
    key = f"papers/{paper_id}/{uuid4()}.pdf"
    await get_storage().put(key, data, "application/pdf")
    if existing:
        old_key = existing.storage_key
        existing.storage_key = key
        existing.file_name = file_name
        existing.file_size = len(data)
        existing.mime_type = "application/pdf"
        existing.uploaded_by = user_id
        existing.processing_status = ProcessingStatus.pending
        existing.processing_error = None
        await get_storage().delete(old_key)
        return existing
    row = PaperFile(
        paper_id=paper_id,
        storage_key=key,
        file_name=file_name,
        file_size=len(data),
        mime_type="application/pdf",
        uploaded_by=user_id,
        processing_status=ProcessingStatus.pending,
    )
    session.add(row)
    await session.flush()
    return row


async def fetch_remote_pdf(session: AsyncSession, paper_id: UUID, user_id: UUID) -> None:
    import httpx

    from app.config import settings

    paper = await session.get(Paper, paper_id)
    if paper is None or not paper.pdf_url:
        return
    existing = await session.scalar(select(PaperFile).where(PaperFile.paper_id == paper_id))
    if existing:
        return
    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as http:
            data = await download_public_pdf(http, paper.pdf_url)
    except Exception:
        logger.exception("remote pdf fetch failed")
        return
    await store_pdf(session, paper_id=paper_id, user_id=user_id, file_name=f"{paper_id}.pdf", data=data)
    await process_stored_pdf(session, paper_id, False)
