import os
import shutil
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="shortlist-tests-"))
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{_TMP / 'test.db'}"
os.environ["UPLOAD_DIR"] = str(_TMP / "uploads")
os.environ["LOG_DIR"] = str(_TMP / "logs")
os.environ["LOG_LEVEL"] = "WARNING"
os.environ["SEED_DEMO_DATA"] = "false"
os.environ.pop("SMTP_HOST", None)
os.environ.pop("ANTHROPIC_API_KEY", None)

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app

import app.services.parser as _parser

_real_ocr, _ocr_cache = _parser._ocr_pdf, {}


def _cached_ocr(content):
    if content not in _ocr_cache:
        _ocr_cache[content] = _real_ocr(content)
    return _ocr_cache[content]


_parser._ocr_pdf = _cached_ocr

SAMPLES = Path(__file__).resolve().parent.parent / "sample_data"
RESUMES = SAMPLES / "resumes"


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_TMP, ignore_errors=True)


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def seeded(client):
    assert client.post("/api/demo/seed").status_code == 200
    return client


def resume_bytes(name: str) -> bytes:
    return (RESUMES / name).read_bytes()


def read_sample(name: str) -> str:
    from app.services.parser import parse_resume

    return parse_resume(name, resume_bytes(name)).text

