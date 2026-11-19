import pytest
from app.config import SAMPLES
from app.main import create_app
@pytest.fixture
def raw(): return (SAMPLES/"dirty.csv").read_bytes()
@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv("DATA_DIR",str(tmp_path));return create_app().test_client()
@pytest.fixture
def isolate(tmp_path,monkeypatch): monkeypatch.setenv("DATA_DIR",str(tmp_path))
