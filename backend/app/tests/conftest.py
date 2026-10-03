import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # One throwaway database per test: seed runs fresh on startup and tests
    # never share a SQLite file (avoids cross-test writer locks).
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    with TestClient(app) as c:
        yield c
