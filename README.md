
# Shortlist — AI-Powered Resume Screening & Candidate Ranking

Paste a job description, drop in a stack of resumes, and get every candidate **ranked by a 0–100 match score** with a
transparent explanation of *why*: which required skills they have, which are missing, and how experience, education
and overall context contributed.

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
