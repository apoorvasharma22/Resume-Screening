from __future__ import annotations

from dataclasses import dataclass

from app.services.extractor import EDU_LEVELS
from app.services.skills import canonical_skill, related_skills, text_mentions

WEIGHTS = {"skills": 0.50, "semantic": 0.20, "experience": 0.20, "education": 0.10}
RELATED_CREDIT = 0.5
KNOCKOUT_RATIO, KNOCKOUT_CAP = 0.25, 45.0


@dataclass
class JobProfile:
    required_skills: list[str]
    preferred_skills: list[str]
    min_experience: float | None
    education_level: str | None


@dataclass
class CandidateProfile:
    skills: list[str]
    experience_years: float
    highest_education: str | None
    raw_text: str
    certifications: list[str]


def verdict_for(score: float) -> str:
    if score >= 75:
        return "Strong match"
    if score >= 60:
        return "Good match"
    if score >= 40:
        return "Partial match"
    return "Weak match"


def _classify(skill: str, cand_set: dict[str, str], text: str) -> str:
    canon = canonical_skill(skill)
    if canon.lower() in cand_set or text_mentions(canon, text):
        return "matched"
    if any(r.lower() in cand_set for r in related_skills(canon)):
        return "related"
    return "missing"


def _classify_group(requirement: str, cand_set: dict[str, str], text: str) -> tuple[str, str]:
    parts = [p.strip() for p in requirement.split("|") if p.strip()]
    results = [(p, _classify(p, cand_set, text)) for p in parts]
    for p, st in results:
        if st == "matched":
            return "matched", p
    label = " or ".join(parts)
    for _, st in results:
        if st == "related":
            return "related", label
    return "missing", label


def _bucket(skills: list[str], cand: CandidateProfile, cand_set: dict[str, str]) -> tuple[list, list, list, float]:
    matched, related, missing = [], [], []
    for s in skills:
        status, label = _classify_group(s, cand_set, cand.raw_text)
        {"matched": matched, "related": related, "missing": missing}[status].append(label)
    credit = len(matched) + RELATED_CREDIT * len(related)
    return matched, related, missing, (credit / len(skills) if skills else 0.0)


def compute_match(job: JobProfile, cand: CandidateProfile, semantic: float) -> dict:
    cand_set = {canonical_skill(s).lower(): s for s in cand.skills}
    for cert in cand.certifications:
        for token in ("aws", "azure", "kubernetes", "scrum"):
            if token in cert.lower():
                cand_set.setdefault(canonical_skill(token).lower(), token)

    canon = lambda g: " | ".join(canonical_skill(p.strip()) for p in g.split("|"))
    req = [canon(s) for s in job.required_skills]
    pref = [canon(s) for s in job.preferred_skills if canon(s) not in req]
    m_req, r_req, x_req, req_ratio = _bucket(req, cand, cand_set)
    m_pref, r_pref, x_pref, pref_ratio = _bucket(pref, cand, cand_set)

    components: dict[str, float | None] = {}
    if req and pref:
        components["skills"] = 0.85 * req_ratio + 0.15 * pref_ratio
    elif req:
        components["skills"] = req_ratio
    elif pref:
        components["skills"] = pref_ratio
    else:
        components["skills"] = None
    components["semantic"] = max(0.0, min(1.0, semantic))

    if job.min_experience:
        components["experience"] = min(1.0, cand.experience_years / job.min_experience)
    else:
        components["experience"] = None

    need = EDU_LEVELS.get(job.education_level or "none", 0)
    have = EDU_LEVELS.get(cand.highest_education or "none", 0)
    components["education"] = None if need == 0 else max(0.0, 1.0 - 0.4 * max(0, need - have))

    active = {k: v for k, v in components.items() if v is not None}
    total_w = sum(WEIGHTS[k] for k in active)
    score = 100 * sum(WEIGHTS[k] * v for k, v in active.items()) / total_w if total_w else 0.0
    knocked_out = bool(req) and req_ratio < KNOCKOUT_RATIO
    if knocked_out:
        score = min(score, KNOCKOUT_CAP)
    score = round(score, 1)

    job_skill_set = {p.strip().lower() for g in req + pref for p in g.split("|")}
    extras = [s for s in cand.skills if canonical_skill(s).lower() not in job_skill_set][:10]

    breakdown = {
        k: {"score": round(100 * components[k], 1) if components[k] is not None else None,
            "weight": round(100 * WEIGHTS[k] / total_w) if components[k] is not None and total_w else 0}
        for k in WEIGHTS
    }
    analysis = {
        "matched_required": m_req, "related_required": r_req, "missing_required": x_req,
        "matched_preferred": m_pref, "related_preferred": r_pref, "missing_preferred": x_pref,
        "extra_skills": extras, "knocked_out": knocked_out,
    }
    return {
        "score": score, "verdict": verdict_for(score), "breakdown": breakdown, "skill_analysis": analysis,
        "summary": _summary(job, cand, analysis, req),
    }


def _summary(job: JobProfile, cand: CandidateProfile, a: dict, req: list[str]) -> str:
    parts = []
    if req:
        parts.append(f"Covers {len(a['matched_required'])} of {len(req)} required skills"
                     + (f" (+{len(a['related_required'])} related)" if a["related_required"] else ""))
    if job.min_experience:
        parts.append(f"{cand.experience_years:g} yrs experience vs {job.min_experience:g} required")
    else:
        parts.append(f"{cand.experience_years:g} yrs experience")
    if job.education_level and job.education_level != "none":
        have = cand.highest_education
        ok = EDU_LEVELS.get(have or "none", 0) >= EDU_LEVELS[job.education_level]
        parts.append(f"{have + ' degree' if have else 'no degree found'}{' meets' if ok else ' is below'} the {job.education_level} requirement" if have else "no degree found on the resume")
    if a["missing_required"]:
        parts.append("missing: " + ", ".join(a["missing_required"][:4]))
    return "; ".join(parts) + "."

