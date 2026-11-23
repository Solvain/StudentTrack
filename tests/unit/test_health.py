from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

from app.db import get_engine
from app.main import app


@pytest.fixture
def engine():
    fake_engine = MagicMock(spec=Engine)
    app.dependency_overrides[get_engine] = lambda: fake_engine
    try:
        yield fake_engine
    finally:
        app.dependency_overrides.pop(get_engine)


def test_health_checks_postgres(engine):
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    connection = engine.connect.return_value.__enter__.return_value
    connection.execute.assert_called_once()
    assert str(connection.execute.call_args.args[0]) == "SELECT 1"


def test_health_returns_unavailable_when_postgres_cannot_connect(engine):
    engine.connect.side_effect = OperationalError(None, None, OSError("connection refused"))

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
