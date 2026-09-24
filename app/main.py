import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select

from app import seed
from app.api.routes import router
from app.config import get_settings
from app.database import SessionLocal, init_db
from app.exceptions import register_exception_handlers
from app.logging_config import get_logger, setup_logging
from app.models import Job

setup_logging()
log = get_logger("shortlist")
settings = get_settings()
STATIC = Path(__file__).parent / "static"

DESCRIPTION = """
**Shortlist** screens resumes against a job description and ranks candidates by fit.

### How it works
1. **Create a job** - paste a description; required / preferred skills, minimum experience and education are extracted automatically (and can be edited).
2. **Upload resumes** (PDF / DOCX, scanned PDFs via OCR) - each is parsed into name, e-mail, phone, skills, education, experience and certifications.
3. **Get a ranking** - every candidate receives a **0-100 match score** with a transparent breakdown
   (skills 50 %, semantic similarity 20 %, experience 20 %, education 10 %) plus the matched, related and missing skills.
4. **Filter, shortlist, export** to Excel / CSV, e-mail shortlisted candidates and generate tailored interview questions.

Errors always use the shape `{"error": {"code": "...", "message": "..."}}`.
"""

TAGS = [
    {"name": "Jobs", "description": "Create and manage the roles you are hiring for."},
    {"name": "Resumes", "description": "Upload and parse resumes."},
    {"name": "Candidates", "description": "Parsed candidate profiles."},
    {"name": "Rankings", "description": "Match scores, filters, shortlisting and export."},
    {"name": "AI extras", "description": "Semantic search, interview questions and e-mail notifications."},
    {"name": "Meta", "description": "Health check and demo data."},
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    if settings.seed_demo_data:
        with SessionLocal() as db:
            if not db.scalar(select(func.count(Job.id))):
                seed.seed_demo(db)
    log.info("%s %s started (db=%s)", settings.app_name, settings.app_version, settings.database_url.split("@")[-1])
    yield


app = FastAPI(title=f"{settings.app_name} - AI Resume Screening API", version=settings.app_version,
              description=DESCRIPTION, openapi_tags=TAGS, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
register_exception_handlers(app)


@app.middleware("http")
async def access_log(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    if request.url.path.startswith("/api"):
        log.info("%s %s -> %s (%.0f ms)", request.method, request.url.path, response.status_code, (time.perf_counter() - start) * 1000)
    return response


app.include_router(router)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")

