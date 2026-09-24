from app.services.jd_parser import parse_job_description

JD = """About the role
We care deeply about accessibility and database design.

Requirements
- 5+ years of experience
- Master's degree in Computer Science, Statistics or a related field
- Strong Python with FastAPI or Django
- PyTorch or TensorFlow
- PostgreSQL and Docker

Nice to have
- Kubernetes
- Kafka experience is a plus
"""


def test_required_and_preferred_are_separated():
    r = parse_job_description(JD)
    assert {"Python", "PostgreSQL", "Docker"} <= set(r["required_skills"])
    assert set(r["preferred_skills"]) == {"Kubernetes", "Kafka"}


def test_either_or_becomes_one_group():
    r = parse_job_description(JD)
    assert "FastAPI | Django" in r["required_skills"]
    assert "PyTorch | TensorFlow" in r["required_skills"]
    assert "Django" not in r["required_skills"]


def test_about_section_and_degree_fields_are_not_skills():
    r = parse_job_description(JD)
    flat = " ".join(r["required_skills"] + r["preferred_skills"])
    assert "Accessibility" not in flat and "Database Design" not in flat
    assert "Statistics" not in flat


def test_experience_and_education():
    r = parse_job_description(JD)
    assert r["min_experience"] == 5.0
    assert r["education_level"] == "master"


def test_lowest_education_wins_when_several_are_named():
    assert parse_job_description("Bachelor's degree required, Master's preferred. Python.")["education_level"] == "bachelor"


def test_plain_degree_means_bachelor_and_no_education_means_none():
    assert parse_job_description("A degree in a relevant field. Python.")["education_level"] == "bachelor"
    assert parse_job_description("Python developer wanted.")["education_level"] is None

