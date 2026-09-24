from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import seed as seeding
from app.database import get_db
from app.exceptions import AppError, NotFoundError
from app.logging_config import get_logger
from app.models import Candidate, Job, Match, NotificationLog
from app.schemas import (
    EducationLevel, InterviewResponse, JobCreate, JobOut, JobParseRequest, JobParseResponse, JobUpdate,
    MatchDetail, MatchOut, MatchStatus, NotifyBulkResponse, NotifyRequest, NotifyResult, RankingResponse,
    SearchResponse, StatusUpdate, UploadItem, UploadResponse, CandidateBrief, CandidateFull,
)
from app.services import embeddings, exporter, interview, notifier, pipeline
from app.services.extractor import EDU_LEVELS
from app.services.jd_parser import parse_job_description
from app.services.skills import canonical_skill, extract_skills, text_mentions

log = get_logger(__name__)
router = APIRouter(prefix="/api")

MIN_SEARCH_SIMILARITY = 0.15
ERR = {404: {"description": "Not found"}, 422: {"description": "Validation error"}}


def _canon_list(skills: list[str]) -> list[str]:
    out = [" | ".join(canonical_skill(p.strip()) for p in s.split("|") if p.strip()) for s in skills]
    return list(dict.fromkeys(x for x in out if x))


def _brief(c: Candidate) -> dict:
    return {"id": c.id, "name": c.name, "email": c.email, "phone": c.phone, "headline": c.headline,
            "experience_years": c.experience_years, "highest_education": c.highest_education,
            "skills": c.skills or [], "certifications": c.certifications or []}


def _full(c: Candidate) -> dict:
    return {**_brief(c), "links": c.links or {}, "education": c.education or [], "experience": c.experience or [],
            "filename": c.filename, "file_type": c.file_type, "parse_method": c.parse_method,
            "parse_warnings": c.parse_warnings or [], "created_at": c.created_at}


def _match_dict(m: Match, rank: int, full: bool = False) -> dict:
    return {"match_id": m.id, "job_id": m.job_id, "rank": rank, "score": m.score, "verdict": m.verdict, "status": m.status,
            "summary": m.summary, "breakdown": m.breakdown, "skill_analysis": m.skill_analysis, "notified_at": m.notified_at,
            "candidate": _full(m.candidate) if full else _brief(m.candidate)}


def _job_out(db: Session, job: Job) -> dict:
    n, avg, top = db.execute(select(func.count(Match.id), func.avg(Match.score), func.max(Match.score)).where(Match.job_id == job.id)).one()
    short = db.scalar(select(func.count(Match.id)).where(Match.job_id == job.id, Match.status == "shortlisted"))
    return {**JobOut.model_validate(job).model_dump(), "candidate_count": n or 0, "shortlisted_count": short or 0,
            "avg_score": round(avg, 1) if avg is not None else None, "top_score": top}


def _ranked(db: Session, job_id: int) -> list[tuple[int, Match]]:
    matches = db.scalars(select(Match).where(Match.job_id == job_id)).all()
    matches.sort(key=lambda m: (-m.score, -(m.candidate.experience_years or 0), m.candidate.name))
    return list(enumerate(matches, 1))


class Filters:

    def __init__(
        self,
        q: str | None = Query(None, description="Search name, e-mail or headline"),
        skills: str | None = Query(None, description="Comma-separated skills, e.g. `python,aws`"),
        skill_mode: Literal["all", "any"] = Query("all", description="Candidate must have ALL or ANY of `skills`"),
        min_experience: float | None = Query(None, ge=0, description="Minimum years of experience"),
        max_experience: float | None = Query(None, ge=0),
        education: EducationLevel | None = Query(None, description="Minimum education level"),
        min_score: float | None = Query(None, ge=0, le=100),
        status: MatchStatus | None = None,
    ):
        self.q, self.skill_mode, self.min_exp, self.max_exp = (q or "").strip().lower(), skill_mode, min_experience, max_experience
        self.education, self.min_score, self.status = education, min_score, status
        self.skills = [canonical_skill(s) for s in (skills or "").split(",") if s.strip()]

    def accepts_candidate(self, c: Candidate) -> bool:
        if self.q and self.q not in f"{c.name} {c.email or ''} {c.headline or ''}".lower():
            return False
        if self.min_exp is not None and c.experience_years < self.min_exp:
            return False
        if self.max_exp is not None and c.experience_years > self.max_exp:
            return False
        if self.education and EDU_LEVELS.get(c.highest_education or "none", 0) < EDU_LEVELS[self.education]:
            return False
        if self.skills:
            have = {canonical_skill(s).lower() for s in c.skills or []}
            hits = [s.lower() in have or text_mentions(s, c.raw_text) for s in self.skills]
            if not (all(hits) if self.skill_mode == "all" else any(hits)):
                return False
        return True

    def accepts_match(self, m: Match) -> bool:
        if self.min_score is not None and m.score < self.min_score:
            return False
        if self.status and m.status != self.status:
            return False
        return self.accepts_candidate(m.candidate)


def _filtered_ranking(db: Session, job_id: int, f: Filters) -> list[dict]:
    return [_match_dict(m, rank) for rank, m in _ranked(db, job_id) if f.accepts_match(m)]


@router.get("/health", tags=["Meta"], summary="Liveness / readiness probe")
def health(db: Session = Depends(get_db)):
    db.execute(select(1))
    return {"status": "ok", "embedding_backend": embeddings.get_embedder().name, "time": datetime.now(timezone.utc)}


@router.post("/demo/seed", tags=["Meta"], summary="Load the bundled sample roles and resumes (idempotent)")
def seed_demo(db: Session = Depends(get_db)):
    return seeding.seed_demo(db)


@router.get("/skills/top", tags=["Meta"], summary="Most common candidate skills (powers filter suggestions)")
def top_skills(limit: int = Query(40, ge=1, le=200), db: Session = Depends(get_db)):
    from collections import Counter

    counts = Counter(s for (skills,) in db.execute(select(Candidate.skills)).all() for s in skills or [])
    return [{"skill": s, "count": n} for s, n in counts.most_common(limit)]


@router.post("/jobs/parse-description", response_model=JobParseResponse, tags=["Jobs"],
             summary="Extract required/preferred skills, experience and education from a job description")
def parse_description(body: JobParseRequest):
    return parse_job_description(body.description)


@router.post("/jobs", response_model=JobOut, status_code=201, tags=["Jobs"],
             summary="Create a job (requirements are auto-extracted unless you provide them) and score all candidates")
def create_job(body: JobCreate, db: Session = Depends(get_db)):
    parsed = parse_job_description(body.description)
    job = Job(
        title=body.title.strip(), company=body.company, description=body.description,
        required_skills=_canon_list(body.required_skills if body.required_skills is not None else parsed["required_skills"]),
        preferred_skills=_canon_list(body.preferred_skills if body.preferred_skills is not None else parsed["preferred_skills"]),
        min_experience=body.min_experience if body.min_experience is not None else parsed["min_experience"],
        education_level=body.education_level or parsed["education_level"],
    )
    db.add(job)
    db.commit()
    pipeline.score_job_against_all(db, job)
    return _job_out(db, job)


@router.get("/jobs", response_model=list[JobOut], tags=["Jobs"], summary="List jobs with screening statistics")
def list_jobs(db: Session = Depends(get_db)):
    return [_job_out(db, j) for j in db.scalars(select(Job).order_by(Job.created_at.desc(), Job.id.desc())).all()]


@router.get("/jobs/{job_id}", response_model=JobOut, tags=["Jobs"], responses=ERR)
def get_job(job_id: int, db: Session = Depends(get_db)):
    return _job_out(db, pipeline.get_job(db, job_id))


@router.put("/jobs/{job_id}", response_model=JobOut, tags=["Jobs"], responses=ERR, summary="Edit a job and re-score all candidates")
def update_job(job_id: int, body: JobUpdate, db: Session = Depends(get_db)):
    job = pipeline.get_job(db, job_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        if k in ("required_skills", "preferred_skills") and v is not None:
            v = _canon_list(v)
        setattr(job, k, v)
    db.commit()
    pipeline.score_job_against_all(db, job)
    return _job_out(db, job)


@router.delete("/jobs/{job_id}", status_code=204, tags=["Jobs"], responses=ERR)
def delete_job(job_id: int, db: Session = Depends(get_db)):
    db.delete(pipeline.get_job(db, job_id))
    db.commit()
    return Response(status_code=204)


@router.post("/resumes/upload", response_model=UploadResponse, tags=["Resumes"],
             summary="Upload one or many resumes (PDF / DOCX). Each is parsed, stored and scored against every job.")
async def upload_resumes(
    files: list[UploadFile] = File(..., description="PDF or DOCX resumes"),
    job_id: int | None = Form(None, description="Optionally return each candidate's score for this job"),
    db: Session = Depends(get_db),
):
    if job_id is not None:
        pipeline.get_job(db, job_id)
    items: list[UploadItem] = []
    for f in files:
        content = await f.read()
        res = pipeline.ingest_resume(db, f.filename or "resume", content)
        item = UploadItem(filename=res.filename, status=res.status, error=res.error)
        if res.candidate:
            c = res.candidate
            item.candidate_id, item.name, item.warnings = c.id, c.name, c.parse_warnings or []
            if job_id is not None:
                m = db.scalar(select(Match).where(Match.job_id == job_id, Match.candidate_id == c.id))
                if m:
                    item.score, item.match_id = m.score, m.id
        items.append(item)
    return UploadResponse(
        processed=sum(i.status in ("processed", "updated") for i in items),
        duplicates=sum(i.status == "duplicate" for i in items),
        failed=sum(i.status == "failed" for i in items), results=items,
    )


@router.get("/candidates", response_model=list[CandidateBrief], tags=["Candidates"], summary="List / filter all candidates")
def list_candidates(f: Filters = Depends(), limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    rows = [c for c in db.scalars(select(Candidate).order_by(Candidate.created_at.desc())).all() if f.accepts_candidate(c)]
    return [_brief(c) for c in rows[offset:offset + limit]]


@router.get("/candidates/{cid}", response_model=CandidateFull, tags=["Candidates"], responses=ERR)
def get_candidate(cid: int, db: Session = Depends(get_db)):
    return _full(pipeline.get_candidate(db, cid))


@router.get("/candidates/{cid}/resume", tags=["Candidates"], responses=ERR, summary="Download the original resume file")
def download_resume(cid: int, db: Session = Depends(get_db)):
    c = pipeline.get_candidate(db, cid)
    path = pipeline.original_path(c)
    if not path.exists():
        raise NotFoundError("The original file is no longer on disk.")
    return FileResponse(path, filename=c.filename)


@router.delete("/candidates/{cid}", status_code=204, tags=["Candidates"], responses=ERR)
def delete_candidate(cid: int, db: Session = Depends(get_db)):
    c = pipeline.get_candidate(db, cid)
    pipeline.original_path(c).unlink(missing_ok=True)
    db.delete(c)
    db.commit()
    return Response(status_code=204)


@router.get("/jobs/{job_id}/rankings", response_model=RankingResponse, tags=["Rankings"], responses=ERR,
            summary="Candidates ranked by match score for a job, with filters")
def rankings(job_id: int, f: Filters = Depends(), limit: int = Query(200, ge=1, le=1000), offset: int = Query(0, ge=0),
             db: Session = Depends(get_db)):
    job = pipeline.get_job(db, job_id)
    items = _filtered_ranking(db, job_id, f)
    return {"job": _job_out(db, job), "total": len(items), "items": items[offset:offset + limit]}


@router.get("/jobs/{job_id}/export", tags=["Rankings"], responses=ERR,
            summary="Export the (filtered) ranking to Excel or CSV",
            response_description="An .xlsx or .csv file download")
def export(job_id: int, format: Literal["xlsx", "csv"] = "xlsx", shortlisted_only: bool = False, f: Filters = Depends(),
           db: Session = Depends(get_db)):
    job = pipeline.get_job(db, job_id)
    if shortlisted_only:
        f.status = "shortlisted"
    items = _filtered_ranking(db, job_id, f)
    slug = "".join(ch if ch.isalnum() else "_" for ch in job.title.lower()).strip("_")
    name = f"shortlist_{slug}_{datetime.now().strftime('%Y%m%d')}"
    log.info("Exporting %d candidates for job %s as %s", len(items), job_id, format)
    if format == "csv":
        return Response(exporter.to_csv(items), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{name}.csv"'})
    data = exporter.to_xlsx(items, JobOut.model_validate(job).model_dump())
    return Response(data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{name}.xlsx"'})


@router.get("/matches/{match_id}", response_model=MatchDetail, tags=["Rankings"], responses=ERR, summary="Full detail for one ranked candidate")
def match_detail(match_id: int, db: Session = Depends(get_db)):
    m = pipeline.get_match(db, match_id)
    rank = next(r for r, x in _ranked(db, m.job_id) if x.id == m.id)
    return _match_dict(m, rank, full=True)


@router.patch("/matches/{match_id}", response_model=MatchOut, tags=["Rankings"], responses=ERR, summary="Shortlist or reject a candidate")
def set_status(match_id: int, body: StatusUpdate, db: Session = Depends(get_db)):
    m = pipeline.get_match(db, match_id)
    m.status = body.status
    db.commit()
    rank = next(r for r, x in _ranked(db, m.job_id) if x.id == m.id)
    return _match_dict(m, rank)


@router.get("/matches/{match_id}/interview-questions", response_model=InterviewResponse, tags=["AI extras"], responses=ERR,
            summary="AI-generated interview questions tailored to this candidate and role")
def interview_questions(match_id: int, count: int = Query(8, ge=3, le=15), db: Session = Depends(get_db)):
    m = pipeline.get_match(db, match_id)
    cand = {**_full(m.candidate), "id": m.candidate.id}
    job = {"id": m.job.id, "title": m.job.title}
    qs, source = interview.generate_questions(cand, job, {"skill_analysis": m.skill_analysis}, count)
    return {"match_id": m.id, "source": source, "questions": qs}


def _notify(db: Session, m: Match, body: NotifyRequest) -> NotifyResult:
    c = m.candidate
    if not c.email:
        return NotifyResult(match_id=m.id, to=None, status="skipped", detail="No email address on this resume.")
    subject, text = notifier.render(c.name, m.job.title, m.job.company, body.subject, body.body)
    try:
        status, err = notifier.send_email(c.email, subject, text), None
    except AppError as exc:
        status, err = "failed", exc.message
    db.add(NotificationLog(match_id=m.id, to_email=c.email, subject=subject, body=text, status=status, error=err))
    if status in ("sent", "dry_run"):
        m.notified_at = datetime.now(timezone.utc)
    db.commit()
    detail = "SMTP is not configured - logged as a dry run, nothing was sent." if status == "dry_run" else err
    return NotifyResult(match_id=m.id, to=c.email, status=status, detail=detail)


@router.post("/matches/{match_id}/notify", response_model=NotifyResult, tags=["AI extras"], responses=ERR,
             summary="E-mail a candidate (dry-run unless SMTP_HOST is configured)")
def notify_one(match_id: int, body: NotifyRequest = NotifyRequest(), db: Session = Depends(get_db)):
    return _notify(db, pipeline.get_match(db, match_id), body)


@router.post("/jobs/{job_id}/notify-shortlisted", response_model=NotifyBulkResponse, tags=["AI extras"], responses=ERR,
             summary="E-mail every shortlisted candidate who has not been notified yet")
def notify_shortlisted(job_id: int, body: NotifyRequest = NotifyRequest(), db: Session = Depends(get_db)):
    pipeline.get_job(db, job_id)
    ms = db.scalars(select(Match).where(Match.job_id == job_id, Match.status == "shortlisted", Match.notified_at.is_(None))).all()
    return {"results": [_notify(db, m, body) for m in ms]}


@router.get("/search", response_model=SearchResponse, tags=["AI extras"],
            summary="Semantic search across all resumes (vector similarity)")
def semantic_search(q: str = Query(..., min_length=2, examples=["experience building LLM apps with retrieval"]),
                    job_id: int | None = Query(None, description="Attach each hit's match score for this job"),
                    limit: int = Query(10, ge=1, le=50), db: Session = Depends(get_db)):
    emb = embeddings.get_embedder()
    qvec = emb.encode([q])[0]
    cands = db.scalars(select(Candidate)).all()
    query_skills = extract_skills(q)
    matches = {}
    if job_id is not None:
        matches = {m.candidate_id: m for m in db.scalars(select(Match).where(Match.job_id == job_id)).all()}
    scored = []
    for c in cands:
        sim = embeddings.calibrate(embeddings.cosine(qvec, pipeline.candidate_vector(c)), emb, kind="query")
        boost = 0.08 * sum(canonical_skill(s).lower() in {canonical_skill(x).lower() for x in c.skills} for s in query_skills)
        scored.append((min(1.0, sim + boost), c))
    db.commit()
    scored.sort(key=lambda t: -t[0])
    hits = []
    for sim, c in scored[:limit]:
        if sim < MIN_SEARCH_SIMILARITY:
            continue
        m = matches.get(c.id)
        terms = [s for s in query_skills if canonical_skill(s).lower() in {canonical_skill(x).lower() for x in c.skills}]
        hits.append({"similarity": round(100 * sim, 1), "matched_terms": terms, "match_id": m.id if m else None,
                     "job_score": m.score if m else None, "candidate": _brief(c)})
    return {"query": q, "backend": emb.name, "hits": hits}

