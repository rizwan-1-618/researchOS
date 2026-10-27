from __future__ import annotations

from collections import Counter
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.algorithms.graph import communities, pagerank, shortest_path
from app.config import settings
from app.models.entities import (
    Author,
    Citation,
    Concept,
    LibraryItem,
    Paper,
    PaperAuthor,
    PaperConcept,
    Project,
    ProjectPaper,
    QuestionPaper,
    ResearchQuestion,
)
from app.models.enums import RelationshipType
from app.schemas.dto import GraphEdge, GraphNode, GraphOut, PathOut, RankedNode
from app.services.support import require_paper, require_row


def node_id(kind: str, value: UUID) -> str:
    return f"{kind}:{value}"


async def build_graph(session: AsyncSession, user_id: UUID, scope: str, focus: UUID | None) -> GraphOut:
    if scope == "project":
        if focus is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A project is required")
        await require_row(session, Project, focus, user_id, "owner_id")
        paper_ids = list(
            (
                await session.scalars(select(ProjectPaper.paper_id).where(ProjectPaper.project_id == focus))
            ).all()
        )
    elif scope == "paper":
        if focus is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A paper is required")
        await require_paper(session, focus)
        paper_ids = [focus]
    elif scope == "authors":
        paper_ids = await _library_ids(session, user_id)
    else:
        paper_ids = await _library_ids(session, user_id)
    paper_ids = paper_ids[: settings.graph_paper_limit]
    neighbor_ids = await _neighbors(session, paper_ids)
    all_paper_ids = list(dict.fromkeys([*paper_ids, *neighbor_ids]))
    papers = list((await session.scalars(select(Paper).where(Paper.id.in_(all_paper_ids)))).all()) if all_paper_ids else []
    library = set(await _library_ids(session, user_id))
    authors = await _authors(session, all_paper_ids)
    concepts = await _concepts(session, user_id, all_paper_ids)
    questions = await _questions(session, user_id, all_paper_ids)
    projects = await _projects(session, user_id, all_paper_ids)
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    paper_nodes = []
    citation_edges = []
    undirected = []
    for paper in papers:
        identifier = node_id("paper", paper.id)
        paper_nodes.append(identifier)
        nodes.append(
            GraphNode(
                id=identifier,
                type="paper",
                label=paper.title,
                data={
                    "year": paper.year,
                    "in_library": paper.id in library,
                    "citation_count": paper.external_citation_count,
                },
            )
        )
    citations = []
    if all_paper_ids:
        citations = (
            await session.execute(
                select(Citation).where(
                    or_(
                        Citation.citing_paper_id.in_(all_paper_ids),
                        Citation.cited_paper_id.in_(all_paper_ids),
                    )
                )
            )
        ).scalars().all()
    seen_edges = set()
    for citation in citations:
        source = node_id("paper", citation.citing_paper_id)
        target = node_id("paper", citation.cited_paper_id)
        key = (source, target, "cites")
        if key in seen_edges:
            continue
        seen_edges.add(key)
        edges.append(GraphEdge(id=f"{source}:{target}:cites", source=source, target=target, type="cites"))
        citation_edges.append((source, target))
        undirected.append((source, target))
    if scope == "authors":
        for paper_id, author in authors:
            author_node = node_id("author", author.id)
            if author_node not in {node.id for node in nodes}:
                nodes.append(
                    GraphNode(
                        id=author_node,
                        type="author",
                        label=author.name,
                        data={"affiliation": author.affiliation},
                    )
                )
            source = node_id("paper", paper_id)
            edges.append(
                GraphEdge(id=f"{source}:{author_node}:written_by", source=source, target=author_node, type="written_by")
            )
            undirected.append((source, author_node))
        by_paper: dict[UUID, list[UUID]] = {}
        for paper_id, author in authors:
            by_paper.setdefault(paper_id, []).append(author.id)
        for grouped in by_paper.values():
            for index, left in enumerate(grouped):
                for right in grouped[index + 1 :]:
                    source = node_id("author", left)
                    target = node_id("author", right)
                    edge_id = f"{source}:{target}:collaborates"
                    if edge_id in seen_edges:
                        continue
                    seen_edges.add(edge_id)
                    edges.append(GraphEdge(id=edge_id, source=source, target=target, type="collaborates"))
                    undirected.append((source, target))
    concept_degree = Counter(concept.id for _paper_id, concept, _relationship in concepts)
    for paper_id, concept, relationship in concepts:
        if concept_degree[concept.id] < 2:
            continue
        concept_node = node_id("concept", concept.id)
        if concept_node not in {node.id for node in nodes}:
            nodes.append(GraphNode(id=concept_node, type="concept", label=concept.name, data={}))
        source = node_id("paper", paper_id)
        edge_type = relationship.value
        edges.append(GraphEdge(id=f"{source}:{concept_node}:{edge_type}", source=source, target=concept_node, type=edge_type))
        undirected.append((source, concept_node))
    for question, paper_id in questions:
        question_node = node_id("question", question.id)
        if question_node not in {node.id for node in nodes}:
            nodes.append(GraphNode(id=question_node, type="question", label=question.title, data={"status": question.status.value}))
        target = node_id("paper", paper_id)
        edges.append(GraphEdge(id=f"{question_node}:{target}:supported_by", source=question_node, target=target, type="supported_by"))
        undirected.append((question_node, target))
    for project, paper_id in projects:
        project_node = node_id("project", project.id)
        if project_node not in {node.id for node in nodes}:
            nodes.append(GraphNode(id=project_node, type="project", label=project.name, data={"status": project.status.value}))
        source = node_id("project", project.id)
        target = node_id("paper", paper_id)
        edges.append(GraphEdge(id=f"{source}:{target}:contains", source=source, target=target, type="contains"))
        undirected.append((source, target))
    ranks = pagerank(paper_nodes, citation_edges)
    groups = communities([node.id for node in nodes], undirected)
    for node in nodes:
        node.community = groups.get(node.id)
        if node.type == "paper":
            node.pagerank = ranks.get(node.id)
    influential = sorted(
        (
            RankedNode(id=node.id, label=node.label, score=node.pagerank)
            for node in nodes
            if node.type == "paper" and node.pagerank is not None
        ),
        key=lambda item: item.score,
        reverse=True,
    )[: settings.influential_limit]
    return GraphOut(nodes=nodes, edges=edges, influential=influential)


async def find_path(session: AsyncSession, user_id: UUID, source: str, target: str) -> PathOut:
    graph = await build_graph(session, user_id, "library", None)
    path = shortest_path(
        [node.id for node in graph.nodes],
        [(edge.source, edge.target) for edge in graph.edges],
        source,
        target,
    )
    if not path:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No path connects those records")
    return PathOut(nodes=path)


async def _library_ids(session, user_id: UUID) -> list[UUID]:
    return list(
        (
            await session.scalars(
                select(LibraryItem.paper_id)
                .where(LibraryItem.user_id == user_id)
                .order_by(LibraryItem.added_at.desc())
            )
        ).all()
    )


async def _neighbors(session, paper_ids: list[UUID]) -> list[UUID]:
    if not paper_ids:
        return []
    rows = (
        await session.execute(
            select(Paper.id)
            .join(Citation, or_(Citation.cited_paper_id == Paper.id, Citation.citing_paper_id == Paper.id))
            .where(or_(Citation.citing_paper_id.in_(paper_ids), Citation.cited_paper_id.in_(paper_ids)))
            .order_by(Paper.external_citation_count.desc().nulls_last())
            .limit(settings.graph_neighbor_limit)
        )
    ).all()
    return [row[0] for row in rows if row[0] not in paper_ids]


async def _authors(session, paper_ids: list[UUID]):
    if not paper_ids:
        return []
    return (
        await session.execute(
            select(PaperAuthor.paper_id, Author)
            .join(Author, Author.id == PaperAuthor.author_id)
            .where(PaperAuthor.paper_id.in_(paper_ids))
            .order_by(PaperAuthor.author_order)
        )
    ).all()


async def _concepts(session, user_id, paper_ids):
    if not paper_ids:
        return []
    return (
        await session.execute(
            select(PaperConcept.paper_id, Concept, PaperConcept.relationship_type)
            .join(Concept, Concept.id == PaperConcept.concept_id)
            .where(PaperConcept.user_id == user_id, PaperConcept.paper_id.in_(paper_ids))
        )
    ).all()


async def _questions(session, user_id, paper_ids):
    if not paper_ids:
        return []
    return (
        await session.execute(
            select(ResearchQuestion, QuestionPaper.paper_id)
            .join(QuestionPaper, QuestionPaper.question_id == ResearchQuestion.id)
            .where(ResearchQuestion.user_id == user_id, QuestionPaper.paper_id.in_(paper_ids))
        )
    ).all()


async def _projects(session, user_id, paper_ids):
    if not paper_ids:
        return []
    return (
        await session.execute(
            select(Project, ProjectPaper.paper_id)
            .join(ProjectPaper, ProjectPaper.project_id == Project.id)
            .where(Project.owner_id == user_id, ProjectPaper.paper_id.in_(paper_ids))
        )
    ).all()
