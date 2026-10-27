from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.responses import Response as FileResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import text

from app.algorithms.transitions import allowed_question_statuses
from app.api.deps import (
    PageParams,
    clear_auth_cookies,
    enforce_auth_rate,
    get_http,
    get_redis,
    get_session,
    get_user,
    pagination,
    set_auth_cookies,
)
from app.config import settings
from app.models.entities import User
from app.models.enums import (
    DiscoverySource,
    ProjectStatus,
    QuestionStatus,
    ReadingStatus,
    RelationshipType,
    ResearchLevel,
    SearchMode,
    TaskPriority,
    TaskStatus,
)
from app.schemas.dto import (
    CollectionIn,
    CollectionUpdate,
    ConceptIn,
    ConceptLinkIn,
    ConceptUpdate,
    DiscoveryOut,
    HealthOut,
    HighlightIn,
    HighlightUpdate,
    IdList,
    ImportIn,
    LibraryUpdate,
    LoginIn,
    MetaOut,
    NoteIn,
    NoteUpdate,
    PaperCreate,
    PaperUpdate,
    ProfileUpdate,
    ProjectIn,
    ProjectUpdate,
    QuestionIn,
    QuestionUpdate,
    RegisterIn,
    TagIn,
    TaskIn,
    TaskUpdate,
    UserOut,
    UserUpdate,
)
from app.services import auth as auth_service
from app.services.authors import author_profile
from app.services.analytics import overview
from app.services.discovery import import_external, search_sources
from app.services.graph import build_graph, find_path
from app.services.library import (
    add_concept_link,
    add_tag,
    citation_lists,
    create_manual,
    create_upload,
    list_library,
    list_tags,
    mark_opened,
    paper_detail,
    remove_concept_link,
    remove_from_library,
    remove_tag,
    update_library,
    update_paper,
    validate_pdf,
)
from app.services.processing import store_pdf
from app.services.queue import try_enqueue
from app.services.recommendations import recommend
from app.services.search import run_search
from app.services.workspace import (
    add_collection_papers,
    collection_out,
    concept_out,
    create_collection,
    create_concept,
    create_highlight,
    create_note,
    create_project,
    create_question,
    create_task,
    delete_collection,
    delete_concept,
    delete_highlight,
    delete_note,
    delete_project,
    delete_question,
    delete_task,
    highlight_out,
    list_collections,
    list_concepts,
    list_highlights,
    list_notes,
    list_projects,
    list_questions,
    list_tasks,
    note_out,
    project_out,
    question_out,
    remove_collection_paper,
    remove_project_paper,
    remove_question_paper,
    set_project_papers,
    set_question_concepts,
    set_question_papers,
    update_collection,
    update_concept,
    update_highlight,
    update_note,
    update_project,
    update_question,
    update_task,
)
from app.storage.files import get_storage
from sqlalchemy import select
from app.models.entities import PaperFile

router = APIRouter(prefix="/api")


async def current_user(request: Request, session=Depends(get_session)) -> User:
    return await get_user(request, session)


@router.get("/health", response_model=HealthOut)
async def health(request: Request, session=Depends(get_session)):
    database = "ok"
    redis_status = "ok"
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        database = "down"
    try:
        await request.app.state.redis.ping()
    except Exception:
        redis_status = "down"
    return HealthOut(status="ok" if database == "ok" and redis_status == "ok" else "degraded", database=database, redis=redis_status)


@router.get("/meta", response_model=MetaOut)
async def meta():
    return MetaOut(
        max_upload_bytes=settings.max_upload_bytes,
        research_levels=[item.value for item in ResearchLevel],
        reading_statuses=[item.value for item in ReadingStatus],
        question_statuses=[item.value for item in QuestionStatus],
        question_transitions={
            item.value: [allowed.value for allowed in allowed_question_statuses(item)] for item in QuestionStatus
        },
        task_statuses=[item.value for item in TaskStatus],
        task_priorities=[item.value for item in TaskPriority],
        project_statuses=[item.value for item in ProjectStatus],
        relationship_types=[item.value for item in RelationshipType],
        search_modes=[item.value for item in SearchMode],
        discovery_sources=[item.value for item in DiscoverySource],
    )


@router.post("/auth/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterIn, response: Response, session=Depends(get_session), _rate=Depends(enforce_auth_rate)):
    user = await auth_service.register_user(session, payload)
    access, refresh = await auth_service.issue_tokens(session, user)
    set_auth_cookies(response, access, refresh)
    return await auth_service.current_user_out(session, user)


@router.post("/auth/login", response_model=UserOut)
async def login(payload: LoginIn, response: Response, session=Depends(get_session), _rate=Depends(enforce_auth_rate)):
    user = await auth_service.authenticate(session, payload.email, payload.password)
    access, refresh = await auth_service.issue_tokens(session, user)
    set_auth_cookies(response, access, refresh)
    return await auth_service.current_user_out(session, user)


@router.post("/auth/token")
async def token(form: OAuth2PasswordRequestForm = Depends(), session=Depends(get_session), _rate=Depends(enforce_auth_rate)):
    user = await auth_service.authenticate(session, form.username, form.password)
    access, _refresh = await auth_service.issue_tokens(session, user)
    return {"access_token": access, "token_type": "bearer"}


@router.post("/auth/refresh", response_model=UserOut)
async def refresh(request: Request, response: Response, session=Depends(get_session)):
    raw = request.cookies.get("refresh_token")
    if not raw:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Could not validate credentials")
    user, access, rotated = await auth_service.rotate_tokens(session, raw)
    set_auth_cookies(response, access, rotated)
    return await auth_service.current_user_out(session, user)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response, session=Depends(get_session)):
    await auth_service.revoke_token(session, request.cookies.get("refresh_token"))
    clear_auth_cookies(response)


@router.get("/auth/me", response_model=UserOut)
async def me(user: User = Depends(current_user), session=Depends(get_session)):
    return await auth_service.current_user_out(session, user)


@router.patch("/users/me", response_model=UserOut)
async def patch_me(payload: UserUpdate, user: User = Depends(current_user), session=Depends(get_session)):
    await auth_service.update_user(session, user, payload)
    return await auth_service.current_user_out(session, user)


@router.put("/users/me/profile", response_model=UserOut)
async def put_profile(payload: ProfileUpdate, user: User = Depends(current_user), session=Depends(get_session)):
    await auth_service.replace_profile(session, user, payload)
    return await auth_service.current_user_out(session, user)


@router.get("/papers")
async def papers(
    status_filter: ReadingStatus | None = Query(default=None, alias="status"),
    important: bool | None = None,
    favorite: bool | None = None,
    tag_id: UUID | None = None,
    collection_id: UUID | None = None,
    project_id: UUID | None = None,
    q: str | None = None,
    page: PageParams = Depends(pagination),
    user: User = Depends(current_user),
    session=Depends(get_session),
):
    return await list_library(
        session,
        user.id,
        limit=page.limit,
        offset=page.offset,
        status_filter=status_filter,
        important=important,
        favorite=favorite,
        tag_id=tag_id,
        collection_id=collection_id,
        project_id=project_id,
        q=q,
    )


@router.post("/papers", status_code=status.HTTP_201_CREATED)
async def post_paper(
    payload: PaperCreate,
    background: BackgroundTasks,
    user: User = Depends(current_user),
    session=Depends(get_session),
    http=Depends(get_http),
):
    paper = await create_manual(session, http, user.id, payload)
    detail = await paper_detail(session, user.id, paper.id)
    if paper.pdf_url:
        background.add_task(try_enqueue, "app.workers.jobs.fetch_pdf", str(paper.id), str(user.id))
    return detail


@router.post("/papers/upload", status_code=status.HTTP_201_CREATED)
async def upload_paper(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    user: User = Depends(current_user),
    session=Depends(get_session),
):
    data = await file.read()
    validate_pdf(data, file.content_type)
    paper, apply_metadata = await create_upload(session, user.id, file.filename or "", title)
    await store_pdf(session, paper_id=paper.id, user_id=user.id, file_name=file.filename or "paper.pdf", data=data)
    background.add_task(try_enqueue, "app.workers.jobs.process_pdf", str(paper.id), apply_metadata)
    return await paper_detail(session, user.id, paper.id)


@router.get("/papers/{paper_id}")
async def get_paper(paper_id: UUID, user: User = Depends(current_user), session=Depends(get_session)):
    return await paper_detail(session, user.id, paper_id)


@router.patch("/papers/{paper_id}")
async def patch_paper(paper_id: UUID, payload: PaperUpdate, user: User = Depends(current_user), session=Depends(get_session)):
    await update_paper(session, user.id, paper_id, payload)
    return await paper_detail(session, user.id, paper_id)


@router.patch("/papers/{paper_id}/library")
async def patch_library(paper_id: UUID, payload: LibraryUpdate, user: User = Depends(current_user), session=Depends(get_session)):
    await update_library(session, user.id, paper_id, payload)
    return await paper_detail(session, user.id, paper_id)


@router.delete("/papers/{paper_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_paper(paper_id: UUID, user: User = Depends(current_user), session=Depends(get_session)):
    await remove_from_library(session, user.id, paper_id)


@router.post("/papers/{paper_id}/file")
async def attach_file(
    paper_id: UUID,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    user: User = Depends(current_user),
    session=Depends(get_session),
):
    from app.services.library import require_saved

    await require_saved(session, user.id, paper_id)
    data = await file.read()
    validate_pdf(data, file.content_type)
    await store_pdf(session, paper_id=paper_id, user_id=user.id, file_name=file.filename or "paper.pdf", data=data)
    background.add_task(try_enqueue, "app.workers.jobs.process_pdf", str(paper_id), False)
    return await paper_detail(session, user.id, paper_id)


@router.get("/papers/{paper_id}/file")
async def download_file(paper_id: UUID, user: User = Depends(current_user), session=Depends(get_session)):
    row = await session.scalar(select(PaperFile).where(PaperFile.paper_id == paper_id))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This paper has no file")
    data = await get_storage().get(row.storage_key)
    return FileResponse(content=data, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{row.file_name}"'})


@router.post("/papers/{paper_id}/opened", status_code=status.HTTP_204_NO_CONTENT)
async def opened(paper_id: UUID, user: User = Depends(current_user), session=Depends(get_session)):
    await mark_opened(session, user.id, paper_id)


@router.post("/papers/{paper_id}/process", status_code=status.HTTP_202_ACCEPTED)
async def reprocess(paper_id: UUID, background: BackgroundTasks, user: User = Depends(current_user), session=Depends(get_session)):
    from app.services.library import require_saved

    await require_saved(session, user.id, paper_id)
    background.add_task(try_enqueue, "app.workers.jobs.process_pdf", str(paper_id), False)
    background.add_task(try_enqueue, "app.workers.jobs.expand_paper_citations", str(paper_id), str(user.id))
    return {"status": "queued"}


@router.get("/papers/{paper_id}/citations")
async def citations(paper_id: UUID, user: User = Depends(current_user), session=Depends(get_session)):
    return await citation_lists(session, user.id, paper_id)


@router.get("/tags")
async def tags(user: User = Depends(current_user), session=Depends(get_session)):
    return await list_tags(session, user.id)


@router.post("/papers/{paper_id}/tags", status_code=status.HTTP_201_CREATED)
async def post_tag(paper_id: UUID, payload: TagIn, user: User = Depends(current_user), session=Depends(get_session)):
    tag = await add_tag(session, user.id, paper_id, payload)
    return {"id": tag.id, "name": tag.name}


@router.delete("/papers/{paper_id}/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(paper_id: UUID, tag_id: UUID, user: User = Depends(current_user), session=Depends(get_session)):
    await remove_tag(session, user.id, paper_id, tag_id)


@router.post("/papers/{paper_id}/concepts", status_code=status.HTTP_204_NO_CONTENT)
async def post_paper_concept(paper_id: UUID, payload: ConceptLinkIn, user: User = Depends(current_user), session=Depends(get_session)):
    await add_concept_link(session, user.id, paper_id, payload)


@router.delete("/papers/{paper_id}/concepts/{concept_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_paper_concept(
    paper_id: UUID,
    concept_id: UUID,
    relationship_type: RelationshipType,
    user: User = Depends(current_user),
    session=Depends(get_session),
):
    await remove_concept_link(session, user.id, paper_id, concept_id, relationship_type)


@router.get("/discover", response_model=DiscoveryOut)
async def discover(
    q: str = Query(min_length=1, max_length=500),
    source: DiscoverySource = DiscoverySource.all,
    page: int = Query(default=1, ge=1),
    limit: int | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    author: str | None = None,
    use_profile: bool = False,
    user: User = Depends(current_user),
    session=Depends(get_session),
    http=Depends(get_http),
):
    resolved = limit or settings.discovery_page_size
    if resolved < 1 or resolved > settings.discovery_max_page_size:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid page size")
    return await search_sources(
        session,
        http,
        user.id,
        query=q,
        source=source,
        page=page,
        limit=resolved,
        year_from=year_from,
        year_to=year_to,
        author=author,
        use_profile=use_profile,
    )


@router.post("/discover/import")
async def import_paper(
    payload: ImportIn,
    background: BackgroundTasks,
    user: User = Depends(current_user),
    session=Depends(get_session),
    http=Depends(get_http),
):
    paper = await import_external(session, http, user.id, payload.source, payload.external_id)
    if payload.project_id:
        await set_project_papers(session, user.id, payload.project_id, [paper.id])
    if payload.collection_id:
        await add_collection_papers(session, user.id, payload.collection_id, [paper.id])
    background.add_task(try_enqueue, "app.workers.jobs.expand_paper_citations", str(paper.id), str(user.id))
    if paper.pdf_url:
        background.add_task(try_enqueue, "app.workers.jobs.fetch_pdf", str(paper.id), str(user.id))
    return await paper_detail(session, user.id, paper.id)


@router.get("/search")
async def search(
    q: str = Query(min_length=1, max_length=500),
    mode: SearchMode = SearchMode.hybrid,
    status_filter: ReadingStatus | None = Query(default=None, alias="status"),
    important: bool | None = None,
    favorite: bool | None = None,
    tag_id: UUID | None = None,
    collection_id: UUID | None = None,
    project_id: UUID | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    author: str | None = None,
    limit: int | None = None,
    user: User = Depends(current_user),
    session=Depends(get_session),
):
    resolved = limit or settings.search_limit
    if resolved < 1 or resolved > settings.api_max_page_size:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid page size")
    return await run_search(
        session,
        user.id,
        query=q,
        mode=mode,
        limit=resolved,
        status_filter=status_filter,
        important=important,
        favorite=favorite,
        tag_id=tag_id,
        collection_id=collection_id,
        project_id=project_id,
        year_from=year_from,
        year_to=year_to,
        author=author,
    )


@router.get("/recommendations")
async def recommendations(user: User = Depends(current_user), session=Depends(get_session), redis=Depends(get_redis), http=Depends(get_http)):
    return await recommend(session, redis, http, user)


@router.get("/graph")
async def graph(
    scope: str = Query(default="library"),
    focus: UUID | None = None,
    user: User = Depends(current_user),
    session=Depends(get_session),
):
    if scope not in {"library", "paper", "project", "authors"}:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown graph scope")
    return await build_graph(session, user.id, scope, focus)


@router.get("/graph/path")
async def graph_path(source: str, target: str, user: User = Depends(current_user), session=Depends(get_session)):
    return await find_path(session, user.id, source, target)


@router.get("/analytics/overview")
async def analytics(user: User = Depends(current_user), session=Depends(get_session)):
    return await overview(session, user.id)


@router.get("/authors/{author_id}")
async def get_author(author_id: UUID, user: User = Depends(current_user), session=Depends(get_session)):
    return await author_profile(session, user.id, author_id)


@router.get("/collections")
async def collections(user: User = Depends(current_user), session=Depends(get_session)):
    return await list_collections(session, user.id)


@router.post("/collections", status_code=status.HTTP_201_CREATED)
async def post_collection(payload: CollectionIn, user: User = Depends(current_user), session=Depends(get_session)):
    row = await create_collection(session, user.id, payload)
    return await collection_out(session, row)


@router.patch("/collections/{collection_id}")
async def patch_collection(collection_id: UUID, payload: CollectionUpdate, user: User = Depends(current_user), session=Depends(get_session)):
    row = await update_collection(session, user.id, collection_id, payload)
    return await collection_out(session, row)


@router.delete("/collections/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_collection(collection_id: UUID, user: User = Depends(current_user), session=Depends(get_session)):
    await delete_collection(session, user.id, collection_id)


@router.post("/collections/{collection_id}/papers", status_code=status.HTTP_204_NO_CONTENT)
async def post_collection_papers(collection_id: UUID, payload: IdList, user: User = Depends(current_user), session=Depends(get_session)):
    await add_collection_papers(session, user.id, collection_id, payload.ids)


@router.delete("/collections/{collection_id}/papers/{paper_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection_paper(collection_id: UUID, paper_id: UUID, user: User = Depends(current_user), session=Depends(get_session)):
    await remove_collection_paper(session, user.id, collection_id, paper_id)


@router.get("/projects")
async def projects(user: User = Depends(current_user), session=Depends(get_session)):
    return await list_projects(session, user.id)


@router.post("/projects", status_code=status.HTTP_201_CREATED)
async def post_project(payload: ProjectIn, user: User = Depends(current_user), session=Depends(get_session)):
    row = await create_project(session, user.id, payload)
    return await project_out(session, user.id, row)


@router.get("/projects/{project_id}")
async def get_project(project_id: UUID, user: User = Depends(current_user), session=Depends(get_session)):
    from app.services.support import require_row
    from app.models.entities import Project

    row = await require_row(session, Project, project_id, user.id, "owner_id")
    return await project_out(session, user.id, row)


@router.patch("/projects/{project_id}")
async def patch_project(project_id: UUID, payload: ProjectUpdate, user: User = Depends(current_user), session=Depends(get_session)):
    row = await update_project(session, user.id, project_id, payload)
    return await project_out(session, user.id, row)


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_project(project_id: UUID, user: User = Depends(current_user), session=Depends(get_session)):
    await delete_project(session, user.id, project_id)


@router.post("/projects/{project_id}/papers", status_code=status.HTTP_204_NO_CONTENT)
async def post_project_papers(project_id: UUID, payload: IdList, user: User = Depends(current_user), session=Depends(get_session)):
    await set_project_papers(session, user.id, project_id, payload.ids)


@router.delete("/projects/{project_id}/papers/{paper_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project_paper(project_id: UUID, paper_id: UUID, user: User = Depends(current_user), session=Depends(get_session)):
    await remove_project_paper(session, user.id, project_id, paper_id)


@router.get("/questions")
async def questions(
    project_id: UUID | None = None,
    status_filter: QuestionStatus | None = Query(default=None, alias="status"),
    user: User = Depends(current_user),
    session=Depends(get_session),
):
    return await list_questions(session, user.id, project_id, status_filter)


@router.post("/questions", status_code=status.HTTP_201_CREATED)
async def post_question(payload: QuestionIn, user: User = Depends(current_user), session=Depends(get_session)):
    row = await create_question(session, user.id, payload)
    return await question_out(session, row)


@router.patch("/questions/{question_id}")
async def patch_question(question_id: UUID, payload: QuestionUpdate, user: User = Depends(current_user), session=Depends(get_session)):
    row = await update_question(session, user.id, question_id, payload)
    return await question_out(session, row)


@router.delete("/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_question(question_id: UUID, user: User = Depends(current_user), session=Depends(get_session)):
    await delete_question(session, user.id, question_id)


@router.post("/questions/{question_id}/papers", status_code=status.HTTP_204_NO_CONTENT)
async def post_question_papers(question_id: UUID, payload: IdList, user: User = Depends(current_user), session=Depends(get_session)):
    await set_question_papers(session, user.id, question_id, payload.ids)


@router.delete("/questions/{question_id}/papers/{paper_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question_paper(question_id: UUID, paper_id: UUID, user: User = Depends(current_user), session=Depends(get_session)):
    await remove_question_paper(session, user.id, question_id, paper_id)


@router.put("/questions/{question_id}/concepts", status_code=status.HTTP_204_NO_CONTENT)
async def put_question_concepts(question_id: UUID, payload: IdList, user: User = Depends(current_user), session=Depends(get_session)):
    await set_question_concepts(session, user.id, question_id, payload.ids)


@router.get("/tasks")
async def tasks(
    project_id: UUID | None = None,
    status_filter: TaskStatus | None = Query(default=None, alias="status"),
    user: User = Depends(current_user),
    session=Depends(get_session),
):
    return await list_tasks(session, user.id, project_id, status_filter)


@router.post("/tasks", status_code=status.HTTP_201_CREATED)
async def post_task(payload: TaskIn, user: User = Depends(current_user), session=Depends(get_session)):
    from app.services.workspace import _task_out

    return _task_out(await create_task(session, user.id, payload))


@router.patch("/tasks/{task_id}")
async def patch_task(task_id: UUID, payload: TaskUpdate, user: User = Depends(current_user), session=Depends(get_session)):
    from app.services.workspace import _task_out

    return _task_out(await update_task(session, user.id, task_id, payload))


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_task(task_id: UUID, user: User = Depends(current_user), session=Depends(get_session)):
    await delete_task(session, user.id, task_id)


@router.get("/concepts")
async def concepts(
    q: str | None = None,
    project_id: UUID | None = None,
    user: User = Depends(current_user),
    session=Depends(get_session),
):
    return await list_concepts(session, user.id, q, project_id)


@router.post("/concepts", status_code=status.HTTP_201_CREATED)
async def post_concept(payload: ConceptIn, user: User = Depends(current_user), session=Depends(get_session)):
    return await concept_out(session, await create_concept(session, user.id, payload))


@router.patch("/concepts/{concept_id}")
async def patch_concept(concept_id: UUID, payload: ConceptUpdate, user: User = Depends(current_user), session=Depends(get_session)):
    return await concept_out(session, await update_concept(session, user.id, concept_id, payload))


@router.delete("/concepts/{concept_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_concept(concept_id: UUID, user: User = Depends(current_user), session=Depends(get_session)):
    await delete_concept(session, user.id, concept_id)


@router.get("/notes")
async def notes(
    paper_id: UUID | None = None,
    project_id: UUID | None = None,
    question_id: UUID | None = None,
    q: str | None = None,
    page: PageParams = Depends(pagination),
    user: User = Depends(current_user),
    session=Depends(get_session),
):
    return await list_notes(
        session,
        user.id,
        limit=page.limit,
        offset=page.offset,
        paper_id=paper_id,
        project_id=project_id,
        question_id=question_id,
        q=q,
    )


@router.post("/notes", status_code=status.HTTP_201_CREATED)
async def post_note(payload: NoteIn, user: User = Depends(current_user), session=Depends(get_session)):
    return await note_out(session, await create_note(session, user.id, payload))


@router.patch("/notes/{note_id}")
async def patch_note(note_id: UUID, payload: NoteUpdate, user: User = Depends(current_user), session=Depends(get_session)):
    return await note_out(session, await update_note(session, user.id, note_id, payload))


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_note(note_id: UUID, user: User = Depends(current_user), session=Depends(get_session)):
    await delete_note(session, user.id, note_id)


@router.get("/highlights")
async def highlights(paper_id: UUID, user: User = Depends(current_user), session=Depends(get_session)):
    return await list_highlights(session, user.id, paper_id)


@router.post("/highlights", status_code=status.HTTP_201_CREATED)
async def post_highlight(payload: HighlightIn, user: User = Depends(current_user), session=Depends(get_session)):
    return await highlight_out(session, await create_highlight(session, user.id, payload))


@router.patch("/highlights/{highlight_id}")
async def patch_highlight(highlight_id: UUID, payload: HighlightUpdate, user: User = Depends(current_user), session=Depends(get_session)):
    return await highlight_out(session, await update_highlight(session, user.id, highlight_id, payload))


@router.delete("/highlights/{highlight_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_highlight(highlight_id: UUID, user: User = Depends(current_user), session=Depends(get_session)):
    await delete_highlight(session, user.id, highlight_id)
