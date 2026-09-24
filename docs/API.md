# API reference

Base URL `http://localhost:8000`. Interactive docs: **`/docs`** (Swagger UI), **`/redoc`**. Machine-readable spec: [`openapi.json`](openapi.json) (import into Postman / Insomnia).

All request/response bodies are JSON unless noted. Errors share one shape:

```json
{ "error": { "code": "not_found", "message": "Job 42 does not exist." } }
```

| HTTP | `code` | When |
|---|---|---|
| 404 | `not_found` | Unknown job / candidate / match id |
| 413 | `file_too_large` | Upload exceeds `MAX_UPLOAD_MB` (single-file errors inside a batch are reported per file instead) |
| 415 | `unsupported_file_type` | Not `.pdf` / `.docx` |
| 422 | `resume_unreadable` / validation | Corrupted file, no text, or invalid request fields |
| 502 | `email_failed` | SMTP failure |
| 500 | `internal_error` | Unexpected; details are in the server log only |

## Jobs
| Method | Path | Description |
|---|---|---|
| POST | `/api/jobs/parse-description` | `{description}` → extracted `required_skills`, `preferred_skills`, `min_experience`, `education_level` (no data saved) |
| POST | `/api/jobs` | Create a job; omitted requirement fields are auto-extracted; scores all existing candidates |
| GET | `/api/jobs` | List jobs with `candidate_count`, `shortlisted_count`, `avg_score`, `top_score` |
| GET/PUT/DELETE | `/api/jobs/{id}` | Read / edit (re-scores everyone) / delete |

`required_skills` entries may be any-of groups: `"FastAPI | Django"`.

## Resumes & candidates
| Method | Path | Description |
|---|---|---|
| POST | `/api/resumes/upload` | `multipart/form-data`: `files` (repeatable), optional `job_id`. Returns per-file `processed` / `updated` / `duplicate` / `failed` with `score` for `job_id`. One bad file never fails the batch. |
| GET | `/api/candidates` | List with filters (below) |
| GET | `/api/candidates/{id}` | Full parsed profile incl. education, experience, warnings |
| GET | `/api/candidates/{id}/resume` | Download the original file |
| DELETE | `/api/candidates/{id}` | Remove candidate and their matches |

Re-uploading the *same file* → `duplicate`. Uploading a *different file with the same e-mail* → `updated` (record replaced, status kept).

## Rankings
| Method | Path | Description |
|---|---|---|
| GET | `/api/jobs/{id}/rankings` | Ranked candidates with score, breakdown and skill analysis |
| GET | `/api/jobs/{id}/export` | `format=xlsx\|csv`, `shortlisted_only=true`, plus any filter below |
| GET | `/api/matches/{id}` | One candidate's full match detail |
| PATCH | `/api/matches/{id}` | `{"status": "new"\|"shortlisted"\|"rejected"}` |

**Filters** (rankings, export, candidates): `q`, `skills` (comma list), `skill_mode` (`all`\|`any`), `min_experience`,
`max_experience`, `education` (minimum: `diploma`\|`bachelor`\|`master`\|`phd`), `min_score`, `status`; rankings also take `limit`, `offset`.
`rank` is always the candidate's position among **all** candidates for the job, even when filtered.

Example ranking item:
```json
{
  "match_id": 12, "job_id": 1, "rank": 1, "score": 94.3, "verdict": "Strong match", "status": "new",
  "summary": "Covers 9 of 9 required skills; 9 yrs experience vs 5 required; master degree meets the bachelor requirement.",
  "breakdown": {
    "skills":     {"score": 100.0, "weight": 50},
    "semantic":   {"score": 78.5,  "weight": 20},
    "experience": {"score": 100.0, "weight": 20},
    "education":  {"score": 100.0, "weight": 10}
  },
  "skill_analysis": {
    "matched_required": ["Python", "PostgreSQL", "Docker"], "related_required": [], "missing_required": [],
    "matched_preferred": ["Kubernetes", "Terraform"], "related_preferred": [], "missing_preferred": ["Leadership or Mentoring"],
    "extra_skills": ["Go", "Elasticsearch"], "knocked_out": false
  },
  "candidate": {"id": 1, "name": "Aarav Mehta", "email": "aarav.mehta@example.com", "experience_years": 9.0, "highest_education": "master", "...": "..."}
}
```

## AI extras
| Method | Path | Description |
|---|---|---|
| GET | `/api/search?q=...&job_id=&limit=` | Semantic search over all resumes. `similarity` is 0–100; results below the noise floor are dropped. |
| GET | `/api/matches/{id}/interview-questions?count=8` | Tailored questions: depth on matched skills, probes for gaps, experience, certifications, behavioural. `source` is `template` or `llm`. |
| POST | `/api/matches/{id}/notify` | E-mail the candidate. Optional `{subject, body}` with `{name}`, `{job_title}`, `{company_part}` placeholders. Returns `sent`, `dry_run` (no SMTP configured) or `failed`. |
| POST | `/api/jobs/{id}/notify-shortlisted` | E-mail every shortlisted candidate not yet notified |

## Meta
| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Liveness + DB check (used by the Docker health check) |
| POST | `/api/demo/seed` | Load the bundled sample roles and resumes (idempotent) |
| GET | `/api/skills/top?limit=40` | Most common candidate skills |
