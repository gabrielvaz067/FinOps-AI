import pytest
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.db import make_engine, session_factory
from backend.app.detection import run_pipeline
from backend.app.main import create_app
from backend.app.migrations import upgrade
from backend.app.synthetic import seed_database

TEST_KEY = "unit-test-key-not-a-real-secret-12345"


@pytest.fixture(scope="session")
def seeded_engine(tmp_path_factory):
    path = tmp_path_factory.mktemp("database") / "test.db"
    engine = make_engine(f"sqlite:///{path.as_posix()}")
    upgrade(engine)
    with session_factory(engine)() as session:
        seed_database(session, count=5000)
        run_pipeline(session)
    yield engine
    engine.dispose()


@pytest.fixture
def session(seeded_engine):
    with session_factory(seeded_engine)() as session:
        yield session
        session.rollback()


@pytest.fixture
def client(seeded_engine):
    settings = Settings(
        _env_file=None, finops_admin_key=TEST_KEY, gemini_api_key="", notification_mode="simulated"
    )
    with TestClient(create_app(settings, seeded_engine)) as client:
        yield client


@pytest.fixture
def auth():
    return {"X-Admin-Key": TEST_KEY}
