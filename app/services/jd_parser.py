from __future__ import annotations

import re

from app.services.extractor import EDU_LEVELS, LEVEL_NAMES
from app.services.skills import find_skills

PREFERRED_HEAD = re.compile(r"nice[\s-]to[\s-]have|preferred|bonus|good[\s-]to[\s-]have|desirable|\bplus\b|optional|extra credit", re.I)
CONTEXT_HEAD = re.compile(r"^(about|overview|who we are|our (company|team|mission)|the (role|company|team|opportunity)|company|location|benefits|perks)", re.I)
REQUIRED_HEAD = re.compile(r"requirements?|must[\s-]have|required|qualifications?|what you.?ll need|what we.?re looking for|you have|skills|responsibilit|what you.?ll do|you will|the job|key duties|duties", re.I)
LEVEL_PATTERNS = {
    "phd": re.compile(r"\bph\.?d\b|\bdoctorate\b", re.I),
    "master": re.compile(r"\bmaster(?:'?s)?\b|\bm\.?tech\b|\bm\.?sc\b|\bmba\b", re.I),
    "bachelor": re.compile(r"\bbachelor(?:'?s)?\b|\bb\.?tech\b|\bb\.?sc\b|\bundergraduate\b", re.I),
    "diploma": re.compile(r"\bdiploma\b", re.I),
}
ANY_LEVEL = re.compile("|".join(p.pattern for p in LEVEL_PATTERNS.values()), re.I)
OR_GAP = re.compile(r"^\s*(?:,\s*)?(?:or|and/or)\s+$", re.I)


def _groups(line: str) -> list[str]:
    found = find_skills(line)
    out: list[list[str]] = []
    prev_end = None
    for canon, start, end in found:
        if out and prev_end is not None and OR_GAP.match(line[prev_end:start]):
            if canon not in out[-1]:
                out[-1].append(canon)
        else:
            out.append([canon])
        prev_end = end
    return [" | ".join(g) for g in out]


def parse_job_description(text: str) -> dict:
    required: list[str] = []
    preferred: list[str] = []
    mode = "required"
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        bullet = line.startswith(("-", "*", "•"))
        is_heading = not bullet and len(line) < 60 and (line.endswith(":") or line.isupper() or not re.search(r"[.,;]", line))
        if is_heading:
            if PREFERRED_HEAD.search(line):
                mode = "preferred"
                continue
            if CONTEXT_HEAD.search(line):
                mode = "context"
                continue
            if REQUIRED_HEAD.search(line):
                mode = "required"
                continue
        if mode == "context" or ANY_LEVEL.search(line):
            continue
        line_mode = "preferred" if PREFERRED_HEAD.search(line) and not is_heading else mode
        (preferred if line_mode == "preferred" else required).extend(_groups(line))

    required = list(dict.fromkeys(required))
    req_members = {p for g in required for p in g.split(" | ")}
    preferred = [g for g in dict.fromkeys(preferred) if not set(g.split(" | ")) <= req_members]

    min_exp = None
    m = re.search(r"(\d{1,2})\s*\+?\s*(?:-|to|–)?\s*(?:\d{1,2}\s*)?(?:\+\s*)?(?:years?|yrs?)", text, re.I)
    if m:
        min_exp = float(m.group(1))

    levels = [EDU_LEVELS[k] for k, p in LEVEL_PATTERNS.items() if p.search(text)]
    if not levels and re.search(r"\bdegree\b", text, re.I):
        levels = [EDU_LEVELS["bachelor"]]
    education = LEVEL_NAMES[min(levels)] if levels else None
    return {"required_skills": required, "preferred_skills": preferred, "min_experience": min_exp, "education_level": education}

