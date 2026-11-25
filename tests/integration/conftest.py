import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def isolated_engine():
    database_url = os.getenv("STUDENTTRACK_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set STUDENTTRACK_TEST_DATABASE_URL to a disposable PostgreSQL database")

    url = make_url(database_url)
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
    if url.drivername != "postgresql+psycopg":
        pytest.fail("STUDENTTRACK_TEST_DATABASE_URL must use PostgreSQL with psycopg")

    schema = f"studenttrack_test_{uuid4().hex}"
    admin = create_engine(url)
    try:
        with admin.begin() as connection:
            connection.execute(text(f"CREATE SCHEMA {schema}"))
        engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
        try:
            yield engine
        finally:
            engine.dispose()
            with admin.begin() as connection:
                connection.execute(text(f"DROP SCHEMA {schema} CASCADE"))
    finally:
        admin.dispose()


@pytest.fixture
def migrated_engine(isolated_engine):
    config = Config(ROOT / "alembic.ini")
    with isolated_engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    return isolated_engine


@pytest.fixture
def session(migrated_engine):
    with Session(migrated_engine) as database_session:
        yield database_session


@pytest.fixture
def client(migrated_engine, monkeypatch):
    monkeypatch.setenv('JWT_SECRET_KEY', 'test-key-' + 'x' * 40)
    from app.db import get_session
    from app.main import app

    def test_session():
        with Session(migrated_engine, expire_on_commit=False) as database_session:
            yield database_session

    app.dependency_overrides[get_session] = test_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_session)
