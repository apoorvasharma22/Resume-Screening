from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EducationLevel = Literal["diploma", "bachelor", "master", "phd"]
MatchStatus = Literal["new", "shortlisted", "rejected"]


class JobParseRequest(BaseModel):
    description: str = Field(min_length=20, description="Free-text job description")


class JobParseResponse(BaseModel):
    required_skills: list[str]
    preferred_skills: list[str]
    min_experience: float | None
    education_level: EducationLevel | None


class JobCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200, examples=["Senior Backend Engineer"])
    company: str | None = Field(None, max_length=200, examples=["Northwind Labs"])
    description: str = Field(min_length=20, description="Full job description text")
    required_skills: list[str] | None = Field(None, description="Leave empty to auto-extract from the description")
    preferred_skills: list[str] | None = None
    min_experience: float | None = Field(None, ge=0, le=45, description="Minimum years of experience")
    education_level: EducationLevel | None = None


class JobUpdate(BaseModel):
    title: str | None = Field(None, min_length=2, max_length=200)
    company: str | None = None
    description: str | None = Field(None, min_length=20)
    required_skills: list[str] | None = None
    preferred_skills: list[str] | None = None
    min_experience: float | None = Field(None, ge=0, le=45)
    education_level: EducationLevel | None = None


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    company: str | None
    description: str
    required_skills: list[str]
    preferred_skills: list[str]
    min_experience: float | None
    education_level: str | None
    created_at: datetime
    candidate_count: int = 0
    shortlisted_count: int = 0
    avg_score: float | None = None
    top_score: float | None = None


class CandidateBrief(BaseModel):
    id: int
    name: str
    email: str | None
    phone: str | None
    headline: str | None
    experience_years: float
    highest_education: str | None
    skills: list[str]
    certifications: list[str]


class CandidateFull(CandidateBrief):
    links: dict[str, str]
    education: list[dict]
    experience: list[dict]
    filename: str
    file_type: str
    parse_method: str
    parse_warnings: list[str]
    created_at: datetime


class ScoreComponent(BaseModel):
    score: float | None = Field(None, description="0-100, null when the job does not specify this criterion")
    weight: int = Field(description="Effective weight in percent after re-normalisation")


class SkillAnalysis(BaseModel):
    matched_required: list[str]
    related_required: list[str]
    missing_required: list[str]
    matched_preferred: list[str]
    related_preferred: list[str]
    missing_preferred: list[str]
    extra_skills: list[str]
    knocked_out: bool


class MatchOut(BaseModel):
    match_id: int
    job_id: int
    rank: int
    score: float = Field(ge=0, le=100)
    verdict: str
    status: MatchStatus
    summary: str
    breakdown: dict[str, ScoreComponent]
    skill_analysis: SkillAnalysis
    notified_at: datetime | None
    candidate: CandidateBrief


class MatchDetail(MatchOut):
    candidate: CandidateFull


class RankingResponse(BaseModel):
    job: JobOut
    total: int = Field(description="Matches after filters")
    items: list[MatchOut]


class StatusUpdate(BaseModel):
    status: MatchStatus


class NotifyRequest(BaseModel):
    subject: str | None = Field(None, description="Supports {name}, {job_title}, {company_part}")
    body: str | None = None


class NotifyResult(BaseModel):
    match_id: int
    to: str | None
    status: Literal["sent", "dry_run", "failed", "skipped"]
    detail: str | None = None


class NotifyBulkResponse(BaseModel):
    results: list[NotifyResult]


class UploadItem(BaseModel):
    filename: str
    status: Literal["processed", "updated", "duplicate", "failed"]
    candidate_id: int | None = None
    name: str | None = None
    score: float | None = Field(None, description="Score against `job_id` when supplied")
    match_id: int | None = None
    warnings: list[str] = []
    error: str | None = None


class UploadResponse(BaseModel):
    processed: int
    duplicates: int
    failed: int
    results: list[UploadItem]


class InterviewQuestion(BaseModel):
    category: str
    question: str
    rationale: str


class InterviewResponse(BaseModel):
    match_id: int
    source: Literal["template", "llm"]
    questions: list[InterviewQuestion]


class SearchHit(BaseModel):
    similarity: float = Field(description="0-100 semantic similarity to the query")
    matched_terms: list[str]
    match_id: int | None = None
    job_score: float | None = None
    candidate: CandidateBrief


class SearchResponse(BaseModel):
    query: str
    backend: str
    hits: list[SearchHit]


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody

