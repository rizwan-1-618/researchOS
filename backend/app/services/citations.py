from __future__ import annotations

import logging
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.integrations import openalex, semantic_scholar
from app.integrations.http import IntegrationError
from app.models.entities import Paper
from app.services.catalog import link_citation, upsert_external
from app.services.support import index_paper

logger = logging.getLogger(__name__)


async def expand_citations(session: AsyncSession, http: httpx.AsyncClient, paper_id: UUID, user_id: UUID) -> None:
    paper = await session.get(Paper, paper_id)
    if paper is None:
        return
    records = []
    try:
        if paper.openalex_id:
            full = await openalex.get_work(http, paper.openalex_id)
            records = await openalex.get_works(http, full.referenced_openalex_ids[: settings.citation_fetch_limit])
        elif paper.semantic_scholar_id:
            full = await semantic_scholar.get_work(http, paper.semantic_scholar_id)
            records = full.references[: settings.citation_fetch_limit]
        else:
            located = None
            if paper.doi:
                located = await openalex.get_work_by_doi(http, paper.doi)
            if located is None and paper.arxiv_id:
                located = await openalex.get_work_by_arxiv(http, paper.arxiv_id)
            if located:
                if not paper.openalex_id:
                    paper.openalex_id = located.openalex_id
                records = await openalex.get_works(
                    http, located.referenced_openalex_ids[: settings.citation_fetch_limit]
                )
    except IntegrationError:
        logger.exception("citation expansion failed")
        return
    for record in records:
        cited = await upsert_external(session, record)
        await link_citation(session, paper.id, cited.id)
        await index_paper(session, cited)
    if records:
        await session.flush()
