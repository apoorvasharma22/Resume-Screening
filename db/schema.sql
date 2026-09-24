CREATE TABLE IF NOT EXISTS jobs (
    id               SERIAL PRIMARY KEY,
    title            VARCHAR(200)  NOT NULL,
    company          VARCHAR(200),
    description      TEXT          NOT NULL,
    required_skills  JSONB         NOT NULL DEFAULT '[]',
    preferred_skills JSONB         NOT NULL DEFAULT '[]',
    min_experience   DOUBLE PRECISION,
    education_level  VARCHAR(20)
        CHECK (education_level IN ('diploma', 'bachelor', 'master', 'phd')),
    created_at       TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS candidates (
    id                SERIAL PRIMARY KEY,
    name              VARCHAR(200)  NOT NULL,
    email             VARCHAR(254),
    phone             VARCHAR(40),
    headline          VARCHAR(200),
    links             JSONB         NOT NULL DEFAULT '{}',
    skills            JSONB         NOT NULL DEFAULT '[]',
    education         JSONB         NOT NULL DEFAULT '[]',
    highest_education VARCHAR(20)
        CHECK (highest_education IN ('diploma', 'bachelor', 'master', 'phd')),
    experience_years  DOUBLE PRECISION NOT NULL DEFAULT 0,
    experience        JSONB         NOT NULL DEFAULT '[]',
    certifications    JSONB         NOT NULL DEFAULT '[]',

    filename          VARCHAR(300)  NOT NULL,
    file_type         VARCHAR(10)   NOT NULL,
    file_hash         VARCHAR(64)   NOT NULL UNIQUE,
    parse_method      VARCHAR(30)   NOT NULL DEFAULT 'text',
    parse_warnings    JSONB         NOT NULL DEFAULT '[]',
    raw_text          TEXT          NOT NULL,

    embedding         BYTEA,
    embedding_backend VARCHAR(60),

    created_at        TIMESTAMPTZ   NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_candidates_email ON candidates (email);

CREATE TABLE IF NOT EXISTS matches (
    id             SERIAL PRIMARY KEY,
    job_id         INTEGER          NOT NULL REFERENCES jobs (id)       ON DELETE CASCADE,
    candidate_id   INTEGER          NOT NULL REFERENCES candidates (id) ON DELETE CASCADE,
    score          DOUBLE PRECISION NOT NULL CHECK (score BETWEEN 0 AND 100),
    verdict        VARCHAR(30)      NOT NULL,
    breakdown      JSONB            NOT NULL DEFAULT '{}',
    skill_analysis JSONB            NOT NULL DEFAULT '{}',
    summary        TEXT             NOT NULL DEFAULT '',
    status         VARCHAR(20)      NOT NULL DEFAULT 'new'
        CHECK (status IN ('new', 'shortlisted', 'rejected')),
    notified_at    TIMESTAMPTZ,
    created_at     TIMESTAMPTZ      NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ      NOT NULL DEFAULT now(),
    CONSTRAINT uq_match_job_candidate UNIQUE (job_id, candidate_id)
);
CREATE INDEX IF NOT EXISTS ix_matches_job_id       ON matches (job_id);
CREATE INDEX IF NOT EXISTS ix_matches_candidate_id ON matches (candidate_id);
CREATE INDEX IF NOT EXISTS ix_matches_score        ON matches (score DESC);
CREATE INDEX IF NOT EXISTS ix_matches_status       ON matches (status);

CREATE TABLE IF NOT EXISTS notification_log (
    id         SERIAL PRIMARY KEY,
    match_id   INTEGER      NOT NULL REFERENCES matches (id) ON DELETE CASCADE,
    to_email   VARCHAR(254) NOT NULL,
    subject    VARCHAR(300) NOT NULL,
    body       TEXT         NOT NULL,
    status     VARCHAR(20)  NOT NULL CHECK (status IN ('sent', 'dry_run', 'failed')),
    error      TEXT,
    created_at TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_notification_log_match_id ON notification_log (match_id);
