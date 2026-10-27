import os

os.environ["DATABASE_URL"] = "postgresql+asyncpg://rizwan@localhost:5432/researchos_test"
os.environ["DATABASE_URL_SYNC"] = "postgresql+psycopg://rizwan@localhost:5432/researchos_test"
os.environ["REDIS_URL"] = "redis://localhost:6379/1"
os.environ["JWT_SECRET"] = "test-secret-test-secret-test-secret-test"
os.environ["EMBEDDING_PROVIDER"] = "fake"
os.environ["STORAGE_BACKEND"] = "local"
os.environ["STORAGE_LOCAL_PATH"] = "/tmp/researchos-test-storage"
os.environ["CONTACT_EMAIL"] = ""

import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.db import new_engine
from app.models import Base


@pytest.fixture(scope="session", autouse=True)
def prepare_db():
    async def setup():
        engine = new_engine()
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(setup())


@pytest.fixture(scope="session")
def client():
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clean(prepare_db):
    yield
    engine = create_engine(os.environ["DATABASE_URL_SYNC"])
    with engine.begin() as conn:
        names = ", ".join(f'"{table.name}"' for table in reversed(Base.metadata.sorted_tables))
        conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
    engine.dispose()
    from redis import Redis

    Redis.from_url(os.environ["REDIS_URL"]).flushdb()
