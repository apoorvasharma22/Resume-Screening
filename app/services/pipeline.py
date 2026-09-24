from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.exceptions import NotFoundError
from app.logging_config import get_logger
from app.models import Candidate, Job, Match
from app.services import embeddings
from app.services.extractor import extract_profile
from app.services.matcher import CandidateProfile, JobProfile, compute_match
from app.services.parser import parse_resume

log = get_logger(__name__)


@dataclass
class IngestResult:
    filename: str
    status: str
    candidate: Candidate | None = None
    error: str | None = None


def job_profile(job: Job) -> JobProfile:
    return JobProfile(job.required_skills or [], job.preferred_skills or [], job.min_experience, job.education_level)


def candidate_profile(c: Candidate) -> CandidateProfile:
    return CandidateProfile(c.skills or [], c.experience_years or 0.0, c.highest_education, c.raw_text, c.certifications or [])


def job_text(job: Job) -> str:
    skills = " ".join((job.required_skills or []) * 2 + (job.preferred_skills or []))
    return f"{job.title}\n{job.description}\n{skills}"


def candidate_vector(c: Candidate):
    emb = embeddings.get_embedder()
    if c.embedding and c.embedding_backend == emb.name:
        return embeddings.from_bytes(c.embedding)
    vec = emb.encode([c.raw_text])[0]
    c.embedding, c.embedding_backend = embeddings.to_bytes(vec), emb.name
    return vec


def _upsert_match(db: Session, job: Job, cand: Candidate, job_vec) -> Match:
    emb = embeddings.get_embedder()
    semantic = embeddings.calibrate(embeddings.cosine(job_vec, candidate_vector(cand)), emb)
    result = compute_match(job_profile(job), candidate_profile(cand), semantic)

    match = db.scalar(select(Match).where(Match.job_id == job.id, Match.candidate_id == cand.id))
    if match is None:
        match = Match(job_id=job.id, candidate_id=cand.id, status="new")
        db.add(match)
    match.score, match.verdict = result["score"], result["verdict"]
    match.breakdown, match.skill_analysis, match.summary = result["breakdown"], result["skill_analysis"], result["summary"]
    match.updated_at = datetime.now(timezone.utc)
    return match


def score_job_against_all(db: Session, job: Job) -> int:
    job_vec = embeddings.get_embedder().encode([job_text(job)])[0]
    candidates = db.scalars(select(Candidate)).all()
    for cand in candidates:
        _upsert_match(db, job, cand, job_vec)
    db.commit()
    log.info("Scored %d candidates for job %s (%s)", len(candidates), job.id, job.title)
    return len(candidates)


def score_candidate_against_all(db: Session, cand: Candidate) -> int:
    emb = embeddings.get_embedder()
    jobs = db.scalars(select(Job)).all()
    for job in jobs:
        _upsert_match(db, job, cand, emb.encode([job_text(job)])[0])
    db.commit()
    return len(jobs)


def ingest_resume(db: Session, filename: str, content: bytes) -> IngestResult:
    from app.exceptions import AppError

    try:
        doc = parse_resume(filename, content)
    except AppError as exc:
        log.warning("Rejected %s: %s", filename, exc.message)
        return IngestResult(filename, "failed", error=exc.message)
    except Exception as exc:
        log.exception("Unexpected parser failure for %s", filename)
        return IngestResult(filename, "failed", error=f"Could not process this file ({type(exc).__name__}).")

    existing = db.scalar(select(Candidate).where(Candidate.file_hash == doc.file_hash))
    if existing:
        return IngestResult(filename, "duplicate", existing)

    profile = extract_profile(doc.text)
    warnings = doc.warnings + profile.pop("warnings")
    emb = embeddings.get_embedder()
    vec = emb.encode([doc.text])[0]

    cand = db.scalar(select(Candidate).where(Candidate.email == profile["email"])) if profile["email"] else None
    status = "updated" if cand else "processed"
    if cand is None:
        cand = Candidate(**profile, filename=filename, file_type=doc.file_type, file_hash=doc.file_hash,
                         parse_method=doc.method, parse_warnings=warnings, raw_text=doc.text)
        db.add(cand)
    else:
        for k, v in profile.items():
            setattr(cand, k, v)
        cand.filename, cand.file_type, cand.file_hash = filename, doc.file_type, doc.file_hash
        cand.parse_method, cand.parse_warnings, cand.raw_text = doc.method, warnings, doc.text
    cand.embedding, cand.embedding_backend = embeddings.to_bytes(vec), emb.name
    db.flush()

    _store_original(cand, content)
    db.commit()
    score_candidate_against_all(db, cand)
    log.info("Ingested %s -> candidate %s (%s)", filename, cand.id, status)
    return IngestResult(filename, status, cand)


def _store_original(cand: Candidate, content: bytes) -> None:
    d = get_settings().upload_dir
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{cand.id}.{cand.file_type}").write_bytes(content)


def original_path(cand: Candidate) -> Path:
    return get_settings().upload_dir / f"{cand.id}.{cand.file_type}"


def get_job(db: Session, job_id: int) -> Job:
    job = db.get(Job, job_id)
    if not job:
        raise NotFoundError(f"Job {job_id} does not exist.")
    return job


def get_candidate(db: Session, cid: int) -> Candidate:
    c = db.get(Candidate, cid)
    if not c:
        raise NotFoundError(f"Candidate {cid} does not exist.")
    return c


def get_match(db: Session, mid: int) -> Match:
    m = db.get(Match, mid)
    if not m:
        raise NotFoundError(f"Match {mid} does not exist.")
    return m

