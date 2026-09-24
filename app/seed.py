from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.logging_config import get_logger
from app.models import Candidate, Job
from app.services.jd_parser import parse_job_description
from app.services.pipeline import ingest_resume, score_job_against_all

log = get_logger(__name__)


def _read_job_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    header, _, body = text.partition("\n\n")
    meta = {k.lower(): v.strip() for k, v in re.findall(r"^(Title|Company|Location):\s*(.+)$", header, re.M)}
    return {"title": meta.get("title", path.stem), "company": meta.get("company"), "description": body.strip()}


def seed_demo(db: Session) -> dict:
    root = get_settings().sample_data_dir
    created_jobs = created_resumes = 0

    if not db.scalar(select(func.count(Job.id))):
        for p in sorted((root / "job_descriptions").glob("*.txt")):
            data = _read_job_file(p)
            parsed = parse_job_description(data["description"])
            db.add(Job(**data, **parsed))
            created_jobs += 1
        db.commit()

    if not db.scalar(select(func.count(Candidate.id))):
        for p in sorted((root / "resumes").glob("*")):
            if p.suffix.lower() in (".pdf", ".docx"):
                res = ingest_resume(db, p.name, p.read_bytes())
                created_resumes += res.status in ("processed", "updated")

    for job in db.scalars(select(Job)).all():
        score_job_against_all(db, job)
    log.info("Demo data ready: %d jobs, %d resumes created", created_jobs, created_resumes)
    return {"jobs_created": created_jobs, "resumes_created": created_resumes}

