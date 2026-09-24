<<<<<<< HEAD
# Shortlist — AI-Powered Resume Screening & Candidate Ranking

Paste a job description, drop in a stack of resumes, and get every candidate **ranked by a 0–100 match score** with a
transparent explanation of *why*: which required skills they have, which are missing, and how experience, education
and overall context contributed.

![Ranking dashboard](docs/screenshots/01-ranking.png)

| | |
|---|---|
| ![Candidate detail](docs/screenshots/02-candidate-detail.png) | ![Semantic search](docs/screenshots/03-semantic-search.png) |

## Requirements checklist

| Requirement | Where it lives |
|---|---|
| **Accept PDF & DOCX** | `app/services/parser.py` – validates type, size and magic bytes |
| **Extract name, email, skills, education, experience, certifications** | `app/services/extractor.py` (+ 200-skill taxonomy in `skills.py`) |
| **Handle different layouts** | Two-column/sidebar PDFs, tables-as-layout DOCX, page headers, wrapped lines, numeric & textual date formats – all covered by the sample set |
| **Match score 0–100, ranking, missing/preferred skills** | `app/services/matcher.py` – see [How scoring works](#how-scoring-works) |
| **Dashboard: upload many, rankings, filters, export** | `app/static/index.html` (served at `/`) |
| **Filters by skills / experience / education** | Dashboard filter bar + the same query params on the API |
| **Export to Excel or CSV** | `GET /api/jobs/{id}/export?format=xlsx\|csv` |
| **Python · NLP · ML/LLM scoring** | Rule-based NLP extraction, TF-hashing / neural embeddings, weighted scoring model |
| **REST API (FastAPI) + Swagger/OpenAPI** | `/docs`, `/redoc`, `/openapi.json`, exported copy in `docs/openapi.json` |
| **PostgreSQL / MySQL** | SQLAlchemy 2; PostgreSQL in Docker; SQLite for zero-config local runs |
| **Logging & exception handling** | Rotating file + console logs, request timing, typed exceptions → uniform JSON errors |
| **Docker** | `Dockerfile` + `docker-compose.yml` (API + PostgreSQL) |
| **Unit testing** | 84 tests (`tests/`), runs on SQLite *and* PostgreSQL |
| **Bonus: semantic search** | `GET /api/search` – vector similarity across all resumes |
| **Bonus: OCR** | Scanned PDFs fall back to Tesseract automatically |
| **Bonus: e-mail notification** | `POST /api/matches/{id}/notify`, bulk for shortlisted; dry-run without SMTP |
| **Bonus: interview questions** | `GET /api/matches/{id}/interview-questions` – tailored to strengths *and* gaps |
| **Deliverables** | Source, API docs (`docs/API.md`, Swagger), DB schema (`db/schema.sql`), README, sample dataset (`sample_data/`) |

## Quick start

### Option A — Deploy to Render (live public link)
1. Push this project to a GitHub repository.
2. Go to [render.com](https://render.com), sign in, click **New +** → **Blueprint**, and pick the repository.
3. Render reads `render.yaml` automatically and creates the `shortlist` web service — click **Apply**.
4. When the build finishes you get a live link, e.g. `https://shortlist.onrender.com`.

The free plan sleeps after 15 minutes idle; the next visit takes ~30 seconds to wake up. `render.yaml` uses SQLite
with demo data seeded automatically (`SEED_DEMO_DATA=true`); switch `DATABASE_URL` to a Render PostgreSQL instance
for persistent, multi-instance storage.

### Option B — Docker (API + PostgreSQL)
```bash
docker compose up --build
```
Open **http://localhost:8000** (dashboard) · **http://localhost:8000/docs** (Swagger). Sample roles and 15 resumes are
loaded on first start (`SEED_DEMO_DATA=true`).

### Option C — local Python (SQLite, no services needed)
```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
SEED_DEMO_DATA=true uvicorn app.main:app --reload       # Windows PowerShell: $env:SEED_DEMO_DATA="true"; uvicorn app.main:app --reload
```
For OCR of scanned PDFs also install the Tesseract binary (`sudo apt install tesseract-ocr`, `brew install tesseract`,
or the Windows installer). Everything else works without it.

### Run the tests
```bash
python -m pytest tests -q                                            # SQLite
TEST_DATABASE_URL=postgresql+psycopg2://user:pass@localhost/db python -m pytest tests -q   # PostgreSQL
```

## Using it

1. **New role** → paste a job description. Required skills, preferred skills, minimum experience and education are
   extracted live and remain editable. Write `FastAPI | Django` for an *either/or* requirement.
2. **Upload resumes** (drag & drop, many at once). Each is parsed and scored against **every** role.
3. **Review the ranking.** The coloured bar on each row shows how the score was built. Click a row for the full
   breakdown, experience timeline, education, certifications and the original file.
4. **Filter** by must-have skills (all/any), minimum years, education, minimum score, or status.
5. **Shortlist** with the ★, then **Export** to Excel/CSV, **email** the shortlist, or generate **interview questions**.

## How scoring works

```
score = 100 × weighted mean of the components the job actually specifies
```

| Component | Weight | How it's measured |
|---|---|---|
| **Skills** | 50 % | 85 % required skills + 15 % preferred. Exact/alias match = 1.0, **related** skill (e.g. MySQL when PostgreSQL is asked) = 0.5. Any-of groups (`A \| B`) need one member. |
| **Context fit** | 20 % | Embedding similarity between the job description and the whole resume, calibrated to 0–1 |
| **Experience** | 20 % | `years / required years`, capped at 1. Years = union of job date ranges (overlaps not double-counted) |
| **Education** | 10 % | Highest degree vs. required level; each missing level costs 40 % |

* If a job doesn't specify a criterion (e.g. no minimum experience) it is **dropped and the other weights re-normalised** – nobody is penalised for what wasn't asked.
* **Knock-out rule:** if fewer than 25 % of required skills are found, the score is capped at 45.
* Verdicts: **≥75 Strong · ≥60 Good · ≥40 Partial · <40 Weak**.

The weights and thresholds are constants at the top of `app/services/matcher.py`.

**Semantic engine.** The default `hashing` backend is deterministic, needs no downloads and works offline: it hashes word
1–2-grams and appends canonical skill tokens so `postgres` and `PostgreSQL` collide. For true neural embeddings run
`pip install -r requirements-optional.txt` and set `EMBEDDING_BACKEND=transformer` (sentence-transformers, MiniLM).

## API

Interactive docs at **`/docs`** (Swagger UI) and **`/redoc`**. Full reference with examples: [`docs/API.md`](docs/API.md).

```bash
# 1. create a role
curl -X POST localhost:8000/api/jobs -H 'content-type: application/json' \
  -d '{"title":"Backend Engineer","description":"Requirements\n- 4+ years\n- Python and FastAPI or Django\n- PostgreSQL and Docker"}'

# 2. upload resumes and see scores for job 1
curl -X POST localhost:8000/api/resumes/upload -F job_id=1 -F files=@sample_data/resumes/aarav_mehta.pdf -F files=@sample_data/resumes/sofia_alvarez.pdf

# 3. ranked candidates, filtered
curl 'localhost:8000/api/jobs/1/rankings?skills=python,docker&min_experience=5&education=bachelor'

# 4. export the shortlist
curl -OJ 'localhost:8000/api/jobs/1/export?format=xlsx&shortlisted_only=true'
```

Errors always look like `{"error": {"code": "unsupported_file_type", "message": "..."}}`.

## Database schema

Four tables (full DDL with comments in [`db/schema.sql`](db/schema.sql); the app also creates them automatically).

```mermaid
erDiagram
    jobs ||--o{ matches : "scored in"
    candidates ||--o{ matches : "has"
    matches ||--o{ notification_log : "emails"
    jobs { int id PK  string title  text description  json required_skills  json preferred_skills  float min_experience  string education_level }
    candidates { int id PK  string name  string email  json skills  json education  float experience_years  json certifications  string file_hash UK  text raw_text  bytea embedding }
    matches { int id PK  int job_id FK  int candidate_id FK  float score  json breakdown  json skill_analysis  string status  timestamp notified_at }
    notification_log { int id PK  int match_id FK  string to_email  string status  text body }
```

`matches` is unique on `(job_id, candidate_id)`. Re-scoring never overwrites a recruiter's `status`.

## Sample dataset

`sample_data/` contains 15 fictional resumes and 3 job descriptions, deliberately varied so the parser is exercised:

| Layout | Files |
|---|---|
| Single-column PDF | Aarav, Rohan, Zara |
| Compact PDF (different headings, `03/2019` dates) | Liam, Meera, Carlos |
| **Two-column sidebar PDF** with full-width header | Sofia, Ananya, Hannah |
| DOCX (classic) | Daniel, Emma, Vikram |
| **DOCX laid out in a table** + page header | Priya, Jonas |
| **Scanned image-only PDF** (needs OCR) | Nikhil |

Regenerate with `python scripts/generate_sample_data.py`. The mix includes strong fits, partial fits, a fresher, a
career-changer and an unrelated HR profile, so rankings are easy to sanity-check.

## Configuration (env vars / `.env`)

See [`.env.example`](.env.example). Key ones: `DATABASE_URL`, `SEED_DEMO_DATA`, `MAX_UPLOAD_MB`, `OCR_ENABLED`,
`EMBEDDING_BACKEND`, `SMTP_*` (blank `SMTP_HOST` = dry run), `ANTHROPIC_API_KEY` (optional LLM-written interview questions).

## Project layout

```
app/
  main.py            FastAPI app, lifespan, middleware, Swagger metadata
  api/routes.py      all REST endpoints + filter logic
  services/
    parser.py        PDF / DOCX / OCR → text (column-aware)
    extractor.py     text → structured profile
    skills.py        skill taxonomy, aliases, related-skill groups
    jd_parser.py     job description → requirements
    matcher.py       scoring model
    embeddings.py    hashing / transformer backends
    pipeline.py      ingest → store → score orchestration
    interview.py · notifier.py · exporter.py
  models.py · schemas.py · database.py · config.py · exceptions.py · logging_config.py
  static/index.html  the dashboard (no build step)
tests/               84 tests: skills, parser, extractor, JD parser, matcher, full API workflow
sample_data/ · db/schema.sql · docs/ · scripts/ · Dockerfile · docker-compose.yml
```

## Design notes & honest limitations

* **A decision aid, not a decision-maker.** Scores rank candidates for human review. Keyword/skill matching can miss
  unconventional but strong candidates and reflects how a resume is written. Keep a person in the loop, and audit
  outcomes for bias before using this in a real hiring process.
* **Rule-based extraction** is fast and explainable but not perfect on highly creative layouts (infographic resumes,
  heavy graphics). Extraction warnings are shown in the candidate panel when something couldn't be found.
* **OCR** quality depends on scan quality; OCR'd resumes are flagged with a warning.
* **Scale.** Filtering/ranking happens in Python over a job's matches – comfortable for thousands of candidates. Beyond
  that, push filters into SQL (JSONB containment is already available in PostgreSQL) and move `ingest_resume` to a task queue.
* **No authentication** – add an auth layer (e.g. an API gateway or FastAPI dependency) before exposing it publicly.
  Resumes contain personal data; apply your retention policy.
* Schema migrations: tables are created with `create_all`; adopt Alembic when the schema starts evolving.

## Verified vs. not verified

Verified in development: the full test suite (SQLite **and** PostgreSQL 16), installing from `requirements-dev.txt`
into a clean virtualenv, `db/schema.sql` on a fresh PostgreSQL database, OCR with Tesseract 5, and the dashboard in headless Chromium (desktop + mobile, incl. a real browser upload).

**Not exercised** in the environment this was built in: building the Docker image (no Docker daemon was available),
sending real SMTP mail, the optional `transformer` embedding backend, and the optional LLM interview-question call
(both fall back safely to the built-in behaviour on any failure).
=======
# Resume-Screening
>>>>>>> e4523cb06e422b67781f2147a4d438356086253e
