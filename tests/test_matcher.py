import pytest

from app.services.matcher import CandidateProfile, JobProfile, compute_match, verdict_for


def cand(skills, years=5, edu="bachelor", text="", certs=()):
    return CandidateProfile(skills, years, edu, text, list(certs))


JOB = JobProfile(["Python", "PostgreSQL", "Docker", "FastAPI | Django"], ["Kubernetes", "Kafka"], 5, "bachelor")


def test_perfect_candidate_scores_high():
    r = compute_match(JOB, cand(["Python", "PostgreSQL", "Docker", "Django", "Kubernetes", "Kafka"]), semantic=1.0)
    assert r["score"] == 100.0
    assert r["verdict"] == "Strong match"
    assert r["skill_analysis"]["missing_required"] == []


def test_either_or_group_is_satisfied_by_one_member():
    r = compute_match(JOB, cand(["Python", "PostgreSQL", "Docker", "FastAPI"]), semantic=0.5)
    assert "FastAPI" in r["skill_analysis"]["matched_required"]
    assert r["skill_analysis"]["missing_required"] == []


def test_missing_group_is_reported_with_both_names():
    r = compute_match(JOB, cand(["Python", "PostgreSQL", "Docker"]), semantic=0.5)
    assert r["skill_analysis"]["missing_required"] == ["FastAPI or Django"]


def test_related_skill_earns_half_credit():
    job = JobProfile(["MySQL"], [], None, None)
    exact = compute_match(job, cand(["MySQL"]), 0.0)["breakdown"]["skills"]["score"]
    related = compute_match(job, cand(["PostgreSQL"]), 0.0)["breakdown"]["skills"]["score"]
    missing = compute_match(job, cand(["Excel"]), 0.0)["breakdown"]["skills"]["score"]
    assert (exact, related, missing) == (100.0, 50.0, 0.0)


def test_experience_scales_linearly_and_caps():
    job = JobProfile([], [], 10, None)
    assert compute_match(job, cand([], years=5), 1.0)["breakdown"]["experience"]["score"] == 50.0
    assert compute_match(job, cand([], years=25), 1.0)["breakdown"]["experience"]["score"] == 100.0


def test_education_gap_is_penalised():
    job = JobProfile([], [], None, "master")
    assert compute_match(job, cand([], edu="master"), 1)["breakdown"]["education"]["score"] == 100.0
    assert compute_match(job, cand([], edu="bachelor"), 1)["breakdown"]["education"]["score"] == 60.0
    assert compute_match(job, cand([], edu=None), 1)["breakdown"]["education"]["score"] == 0.0


def test_unspecified_criteria_are_dropped_and_weights_renormalised():
    job = JobProfile(["Python"], [], None, None)
    r = compute_match(job, cand(["Python"], years=0, edu=None), semantic=1.0)
    assert r["breakdown"]["experience"] == {"score": None, "weight": 0}
    assert r["breakdown"]["education"] == {"score": None, "weight": 0}
    assert r["score"] == 100.0
    assert r["breakdown"]["skills"]["weight"] + r["breakdown"]["semantic"]["weight"] == 100


def test_knockout_cap_when_required_skills_are_absent():
    job = JobProfile(["Python", "Go", "Rust", "Kafka"], [], 1, None)
    r = compute_match(job, cand(["Excel"], years=20, edu="phd"), semantic=1.0)
    assert r["skill_analysis"]["knocked_out"] is True
    assert r["score"] <= 45.0


def test_skill_found_in_free_text_counts_even_if_not_in_skill_list():
    r = compute_match(JobProfile(["Docker"], [], None, None), cand([], text="I containerised everything with Docker"), 0.0)
    assert r["skill_analysis"]["matched_required"] == ["Docker"]


def test_certification_counts_as_cloud_evidence():
    r = compute_match(JobProfile(["AWS"], [], None, None), cand([], certs=["AWS Certified Cloud Practitioner"]), 0.0)
    assert r["skill_analysis"]["matched_required"] == ["AWS"]


def test_score_is_always_between_0_and_100():
    for sem in (-1, 0, 0.3, 1, 5):
        r = compute_match(JOB, cand(["Python"], years=100), sem)
        assert 0 <= r["score"] <= 100


@pytest.mark.parametrize("score,label", [(90, "Strong match"), (75, "Strong match"), (60, "Good match"), (45, "Partial match"), (10, "Weak match")])
def test_verdict_bands(score, label):
    assert verdict_for(score) == label

