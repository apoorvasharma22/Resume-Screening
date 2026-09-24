from __future__ import annotations

import json
import random
import re

from app.config import get_settings
from app.logging_config import get_logger
from app.services.skills import skill_category

log = get_logger(__name__)

TECH_TEMPLATES = {
    "Programming Language": [
        "You use {s} regularly. Describe a piece of {s} code you're proud of and what you'd refactor today.",
        "What {s} features or idioms do you rely on most, and where have they bitten you?",
    ],
    "Database": [
        "Walk me through diagnosing a slow {s} query in production. What do you check first?",
        "How did you design the schema and indexes for a {s}-backed feature, and what trade-offs did you make?",
    ],
    "Cloud & DevOps": [
        "Describe a deployment or outage involving {s} that went wrong. What did you change afterwards?",
        "How have you used {s} to make releases safer or faster?",
    ],
    "Data & ML": [
        "Tell me about a project where you applied {s}. How did you validate that it actually worked?",
        "What are the most common failure modes you have seen with {s} and how do you guard against them?",
    ],
    "Backend": [
        "Explain how you'd design a service using {s} to handle 10x its current traffic.",
        "What mistakes have you made with {s} that you would not repeat?",
    ],
    "Frontend": [
        "How do you structure state and components in a large {s} application?",
        "Describe a performance or accessibility problem you fixed in a {s} app.",
    ],
    "default": [
        "Your resume lists {s}. Tell me about the hardest problem you solved with it.",
        "How do you keep your {s} skills current, and what would you tell a newcomer to avoid?",
    ],
}
BEHAVIOURAL = [
    "Tell me about a time you disagreed with a teammate on a technical decision. How was it resolved?",
    "Describe a project that missed its deadline. What was your role and what did you learn?",
    "Give an example of feedback that changed how you work.",
]


def _template_questions(cand: dict, job: dict, match: dict, n: int) -> list[dict]:
    rng = random.Random(cand["id"] * 31 + job["id"])
    a = match["skill_analysis"]
    qs: list[dict] = []

    generic = {"REST APIs", "Microservices", "CI/CD", "SQL", "Git", "Agile", "Communication", "Leadership", "HTML", "CSS"}
    ordered = [x for x in a["matched_required"] if x not in generic] + [x for x in a["matched_required"] if x in generic]
    for skill in ordered[:4]:
        tpl = TECH_TEMPLATES.get(skill_category(skill), TECH_TEMPLATES["default"])
        qs.append({"category": "Technical depth", "question": rng.choice(tpl).format(s=skill),
                   "rationale": f"{skill} is required for this role and appears on the resume - test real depth."})

    for skill in (a["missing_required"] + a["related_required"])[:2]:
        qs.append({"category": "Gap probing",
                   "question": f"This role relies on {skill}, which isn't clearly on your resume. Where have you worked with something similar, and how would you get productive quickly?",
                   "rationale": f"Required skill '{skill}' was not found - check for transferable experience."})

    years, title = cand["experience_years"], (cand.get("experience") or [{}])[0].get("title") or cand.get("headline")
    if years < 2:
        qs.append({"category": "Experience", "question": "Walk me through your strongest project or internship end to end: the problem, your part, and the outcome.",
                   "rationale": "Early-career profile - probe ownership and learning speed."})
    else:
        qs.append({"category": "Experience",
                   "question": f"You have about {years:g} years of experience" + (f", most recently as \"{title}\"" if title else "")
                               + ". Which project best shows the scope you're ready to own here, and what was your measurable impact?",
                   "rationale": "Connect past scope to the seniority this role needs."})

    if cand.get("certifications"):
        qs.append({"category": "Certifications", "question": f"You hold \"{cand['certifications'][0]}\". What did preparing for it teach you that you use day to day?",
                   "rationale": "Verify the certification translates into practice."})

    for extra in a.get("matched_preferred", [])[:1]:
        qs.append({"category": "Bonus skill", "question": f"You also list {extra}, which is a plus for this role. Where has it made a real difference?",
                   "rationale": "Preferred skill present - assess how strong it is."})

    behavioural = {"category": "Behavioural", "question": rng.choice(BEHAVIOURAL), "rationale": "Collaboration and ownership signal."}
    return qs[: max(n - 1, 0)] + [behavioural]


def _llm_questions(cand: dict, job: dict, match: dict, n: int) -> list[dict] | None:
    key = get_settings().anthropic_api_key
    if not key:
        return None
    import httpx

    prompt = (
        f"Write {n} interview questions for this candidate applying to '{job['title']}'.\n"
        f"Candidate: {cand['name']}, {cand['experience_years']} yrs, skills: {', '.join(cand['skills'][:20])}.\n"
        f"Required skills missing from resume: {', '.join(match['skill_analysis']['missing_required']) or 'none'}.\n"
        "Mix technical depth, gap probing and behavioural. Reply ONLY with a JSON array of objects with keys "
        '"category", "question", "rationale".'
    )
    try:
        r = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": get_settings().llm_model, "max_tokens": 1500, "messages": [{"role": "user", "content": prompt}]},
            timeout=30,
        )
        r.raise_for_status()
        text = "".join(b.get("text", "") for b in r.json()["content"])
        data = json.loads(re.search(r"\[.*\]", text, re.S).group(0))
        return [{"category": str(q["category"]), "question": str(q["question"]), "rationale": str(q.get("rationale", ""))} for q in data][:n]
    except Exception as exc:
        log.warning("LLM interview generation failed, using templates: %s", exc)
        return None


def generate_questions(cand: dict, job: dict, match: dict, n: int = 8) -> tuple[list[dict], str]:
    llm = _llm_questions(cand, job, match, n)
    if llm:
        return llm, "llm"
    return _template_questions(cand, job, match, n), "template"

