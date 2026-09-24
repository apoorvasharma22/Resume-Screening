from __future__ import annotations

import re
from datetime import date

from app.services.skills import AMBIGUOUS_PLAIN, CATEGORY, canonical_skill, extract_skills

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}")
PHONE_CANDIDATE_RE = re.compile(r"\+?\(?\d[\d\s().\-]{8,18}\d")
LINKEDIN_RE = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[A-Za-z0-9\-_%]+", re.I)
GITHUB_RE = re.compile(r"(?:https?://)?(?:www\.)?github\.com/[A-Za-z0-9\-_]+", re.I)

EDU_LEVELS = {"none": 0, "diploma": 1, "bachelor": 2, "master": 3, "phd": 4}
LEVEL_NAMES = {v: k for k, v in EDU_LEVELS.items()}

SECTION_ALIASES = {
    "experience": ["experience", "work experience", "professional experience", "employment history", "work history",
                   "career history", "employment", "relevant experience", "professional background"],
    "education": ["education", "academic background", "academics", "qualifications", "education & training",
                  "education and training", "academic qualifications"],
    "skills": ["skills", "technical skills", "core competencies", "key skills", "skills & tools", "technologies",
               "tech stack", "skills and tools", "areas of expertise", "expertise", "technical expertise"],
    "certifications": ["certifications", "certificates", "licenses", "licenses & certifications", "certifications & licenses",
                       "courses", "training", "training & certifications", "certifications and training"],
    "projects": ["projects", "key projects", "personal projects", "academic projects", "selected projects"],
    "summary": ["summary", "professional summary", "profile", "objective", "about me", "career objective",
                "about", "career summary", "executive summary"],
    "other": ["languages", "interests", "hobbies", "awards", "achievements", "publications", "references",
              "volunteering", "declaration", "personal details", "contact", "links"],
}
HEADING_LOOKUP = {a: k for k, v in SECTION_ALIASES.items() for a in v}

ROLE_WORDS = {
    "engineer", "developer", "manager", "analyst", "scientist", "designer", "consultant", "architect", "specialist",
    "officer", "lead", "director", "intern", "administrator", "programmer", "resume", "curriculum", "vitae", "cv",
    "profile", "summary", "objective", "contact", "email", "phone", "address", "experience", "education", "skills",
    "recruiter", "executive", "associate", "senior", "junior", "full", "stack", "backend", "frontend", "data",
    "machine", "learning", "software", "technical", "professional", "generalist", "coordinator", "head", "principal",
    "engineering", "graduate", "student", "fresher", "trainee", "developer", "devops", "administrator", "staff",
}

_MONTHS = ("jan feb mar apr may jun jul aug sep oct nov dec").split()
_M = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
_MON = rf"(?:{_M}|0?[1-9]|1[0-2])"
RANGE_RE = re.compile(
    rf"(?:(?P<sm>{_MON})[\s/.,]+)?(?P<sy>(?:19|20)\d{{2}})\s*(?:-|–|—|to|until)\s*"
    rf"(?:(?:(?P<em>{_MON})[\s/.,]+)?(?P<ey>(?:19|20)\d{{2}})|(?P<pres>present|current|now|ongoing|today|till\s+date|to\s+date))",
    re.I,
)
EDU_LINE_HINT = re.compile(r"university|college|institute|school|cgpa|gpa|b\.?tech|m\.?tech|bachelor|master|degree|diploma|ph\.?d", re.I)

DEGREE_PATTERNS = [
    ("phd", re.compile(r"\bph\.?\s?d\b|\bdoctorate\b|\bdoctor of philosophy\b", re.I)),
    ("master", re.compile(r"\bmaster(?:'?s)?\b|\bpost[\s-]?graduate\b|\bm\.?\s?tech\b|\bm\.?\s?sc\b|\bmba\b|\bmca\b|\bm\.?\s?eng\b|\bpgdm\b", re.I)),
    ("master", re.compile(r"\b(?:M\.?S|M\.?E|M\.?A|M\.?Com)\b\.?(?=\s|,|\(|$|in\b)")),
    ("bachelor", re.compile(r"\bbachelor(?:'?s)?\b|\bb\.?\s?tech\b|\bb\.?\s?sc\b|\bb\.?\s?eng\b|\bbca\b|\bbba\b|\bundergraduate\b|\bb\.?\s?com\b", re.I)),
    ("bachelor", re.compile(r"\b(?:B\.?S|B\.?E|B\.?A)\b\.?(?=\s|,|\(|$|in\b)")),
    ("diploma", re.compile(r"\bdiploma\b|\bassociate(?:'?s)? degree\b", re.I)),
]

CERT_PATTERNS = [
    re.compile(r"AWS Certified[\w\s\-–:&]+?(?=\s*(?:[,;|(\n]|\d{4}|$))", re.I),
    re.compile(r"Certified Kubernetes (?:Administrator|Application Developer)(?:\s*\(\w+\))?", re.I),
    re.compile(r"Google (?:Cloud )?(?:Certified|Professional)[\w\s\-–:&]+?(?=\s*(?:[,;|(\n]|\d{4}|$))", re.I),
    re.compile(r"Microsoft Certified[\w\s\-–:&]+?(?=\s*(?:[,;|(\n]|\d{4}|$))", re.I),
    re.compile(r"Azure [\w\s]+ (?:Associate|Expert|Fundamentals)", re.I),
    re.compile(r"\b(?:PMP|CISSP|CKAD|CKA|CISA|CEH|ITIL|PRINCE2)\b"),
    re.compile(r"Certified Scrum Master|Professional Scrum Master|Certified ScrumMaster", re.I),
    re.compile(r"TensorFlow Developer Certificate|Databricks Certified[\w\s\-]+|Snowflake SnowPro[\w\s\-]*", re.I),
    re.compile(r"Oracle Certified[\w\s\-]+?(?=\s*(?:[,;|(\n]|\d{4}|$))", re.I),
    re.compile(r"HashiCorp Certified[\w\s:\-]+?(?=\s*(?:[,;|(\n]|\d{4}|$))", re.I),
    re.compile(r"(?:SHRM|PHR|SPHR)[\w\s\-]*(?:CP|SCP)?\b"),
]


def _lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def _heading_key(line: str) -> str | None:
    if len(line) > 48:
        return None
    norm = re.sub(r"[^a-z& ]", "", line.lower()).strip()
    norm = re.sub(r"\s+", " ", norm)
    return HEADING_LOOKUP.get(norm)


def split_sections(lines: list[str]) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {"header": []}
    current = "header"
    inline = re.compile(r"^([A-Za-z &/]{3,32}?)\s*[:\-–]\s*(\S.*)$")
    for line in lines:
        key = _heading_key(line)
        if key:
            current = key
            sections.setdefault(key, [])
            continue
        m = inline.match(line)
        if m and (k := _heading_key(m.group(1))) in ("skills", "certifications", "summary"):
            current = k
            sections.setdefault(k, []).append(m.group(2))
            continue
        sections.setdefault(current, []).append(line)
    return sections


def _strip_bullet(line: str) -> str:
    return re.sub(r"^[\-*•\u2022\s]+", "", line).strip()


def extract_email(text: str) -> str | None:
    m = EMAIL_RE.search(text)
    return m.group(0).lower().rstrip(".") if m else None


def extract_phone(text: str) -> str | None:
    head = "\n".join(text.splitlines()[:25])
    for chunk in (head, text):
        for m in PHONE_CANDIDATE_RE.finditer(chunk):
            raw = m.group(0).strip()
            digits = re.sub(r"\D", "", raw)
            if not 10 <= len(digits) <= 13:
                continue
            if re.search(r"(?:19|20)\d{2}\D{1,4}(?:19|20)\d{2}", raw):
                continue
            return re.sub(r"\s+", " ", raw)
    return None


def extract_links(text: str) -> dict[str, str]:
    links = {}
    if m := LINKEDIN_RE.search(text):
        links["linkedin"] = m.group(0)
    if m := GITHUB_RE.search(text):
        links["github"] = m.group(0)
    return links


def extract_name(lines: list[str], email: str | None) -> str:
    for raw in lines[:15]:
        line = re.sub(r"^(?:full\s+)?name\s*[:\-]\s*", "", raw, flags=re.I).strip()
        if not line or "@" in line or re.search(r"\d", line) or "http" in line.lower() or len(line) > 45:
            continue
        tokens = line.replace(",", " ").split()
        if not 2 <= len(tokens) <= 4:
            continue
        if any(t.lower().strip(".,") in ROLE_WORDS for t in tokens) or "," in line and len(tokens) == 3:
            continue
        if any(canonical_skill(t.strip(".,")) in CATEGORY for t in tokens):
            continue
        if all(re.fullmatch(r"[^\W\d_][\w.'\-]*", t) for t in tokens) and all(t[0].isupper() for t in tokens):
            return line.title() if line.isupper() else line
    if email:
        local = re.split(r"[._\-\d]+", email.split("@")[0])
        words = [w for w in local if len(w) > 1]
        if words:
            return " ".join(w.capitalize() for w in words[:3])
    return "Unknown Candidate"


def extract_headline(header_lines: list[str], name: str, experience: list[dict]) -> str | None:
    for line in header_lines[:8]:
        if name.lower() in line.lower() or "@" in line or re.search(r"\d{5}", line) or len(line) > 70:
            continue
        if any(w.lower().strip(",|") in ROLE_WORDS - {"summary", "profile", "objective", "contact", "email", "phone",
                                                       "address", "experience", "education", "skills", "resume", "cv"}
               for w in line.split()):
            return line.strip(" |-")
    return experience[0]["title"] if experience else None


def _month_num(tok: str | None, default: int) -> int:
    if not tok:
        return default
    tok = tok.strip().lower()
    if tok.isdigit():
        return int(tok)
    return _MONTHS.index(tok[:3]) + 1


def _range_to_months(m: re.Match, today: date) -> tuple[int, int]:
    sy = int(m.group("sy"))
    sm = _month_num(m.group("sm"), 6)
    if m.group("pres"):
        ey, em = today.year, today.month
    else:
        ey = int(m.group("ey"))
        em = _month_num(m.group("em"), 6)
    return sy * 12 + sm, ey * 12 + em


def extract_experience(sections: dict[str, list[str]], today: date | None = None) -> tuple[float, list[dict]]:
    today = today or date.today()
    if sections.get("experience"):
        pool = sections["experience"]
    else:
        pool = [ln for k, v in sections.items() if k not in ("education", "certifications", "other") for ln in v]

    intervals: list[tuple[int, int]] = []
    entries: list[dict] = []
    for i, line in enumerate(pool):
        if EDU_LINE_HINT.search(line) and not sections.get("experience"):
            continue
        for m in RANGE_RE.finditer(line):
            start, end = _range_to_months(m, today)
            if end < start or end - start > 12 * 45:
                continue
            intervals.append((start, end))
            title = re.sub(r"[|,\-–—:()\s]+$", "", RANGE_RE.sub("", line)).strip(" |,-–—:")
            has_role = lambda t: any(w.lower().strip(",|-") in ROLE_WORDS for w in t.split())
            if len(title) < 3 and i > 0:
                title = pool[i - 1]
            elif i > 0 and not has_role(title) and has_role(pool[i - 1]) and not RANGE_RE.search(pool[i - 1]):
                title = f"{pool[i - 1]} - {title}"
            entries.append({"title": title[:140], "period": m.group(0).strip(), "months": end - start})

    intervals.sort()
    merged: list[list[int]] = []
    for s, e in intervals:
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    computed = sum(e - s for s, e in merged) / 12

    explicit = 0.0
    full = "\n".join(pool + sections.get("summary", []) + sections.get("header", []))
    for pat in (
        r"(\d{1,2}(?:\.\d)?)\s*\+?\s*(?:years?|yrs?)(?:\s+of)?(?:\s+[\w/&\-]+){0,4}?\s+experience",
        r"experience\s+(?:of\s+|over\s+)?(\d{1,2}(?:\.\d)?)\s*\+?\s*(?:years?|yrs?)",
    ):
        for m in re.finditer(pat, full, re.I):
            explicit = max(explicit, float(m.group(1)))

    years = min(max(computed, explicit if explicit <= 45 else 0.0), 45.0)
    return round(years, 1), entries[:8]


def extract_education(sections: dict[str, list[str]], full_lines: list[str]) -> tuple[list[dict], str | None]:
    pool = sections.get("education") or [ln for ln in full_lines if EDU_LINE_HINT.search(ln)]
    entries: list[dict] = []
    is_degree = [any(pat.search(ln) for _, pat in DEGREE_PATTERNS) for ln in pool]
    for i, line in enumerate(pool):
        level = next((lvl for lvl, pat in DEGREE_PATTERNS if pat.search(line)), None)
        if not level:
            continue
        block = [line]
        for j in range(i + 1, min(i + 4, len(pool))):
            if is_degree[j]:
                break
            block.append(pool[j])
        inst_pat = r"universi\w*|institut\w*|college|school|\biit\b|\bnit\b|\biiit\b|academy|polit[eé]cnica|technische"
        k = next((n for n, b in enumerate(block) if re.search(inst_pat, b, re.I)), None)
        inst = block[k] if k is not None else None
        if k is not None and k + 1 < len(block) and not re.search(r"(?:19|20)\d{2}", block[k + 1]):
            inst = f"{inst} {block[k + 1]}"
        years = re.findall(r"(?:19|20)\d{2}", " ".join(block))
        field_m = re.search(r"(?:\bin|\bof)\s+([A-Z][A-Za-z&,\- ]{3,50}?)(?=\s*(?:[,(|\-–—]|from\b|at\b|\d{4}|$))", line)
        entries.append({
            "degree": line[:140],
            "level": level,
            "field": field_m.group(1).strip() if field_m else None,
            "institution": inst[:140] if inst and inst != line else None,
            "year": int(years[-1]) if years else None,
        })
    best = max((EDU_LEVELS[e["level"]] for e in entries), default=0)
    return entries, (LEVEL_NAMES[best] if best else None)


def extract_certifications(sections: dict[str, list[str]], text: str) -> list[str]:
    found: dict[str, str] = {}

    def add(c: str) -> None:
        c = re.sub(r"\s+", " ", c).strip(" -–—,;:|")
        if 3 <= len(c) <= 120:
            found.setdefault(re.sub(r"\W+", "", c.lower()), c)

    merged: list[str] = []
    for line in sections.get("certifications", []):
        line = _strip_bullet(line)
        if merged and (merged[-1].endswith(("-", "–", "&", ",", ":")) or line[:1].islower()):
            merged[-1] = f"{merged[-1]} {line}"
        else:
            merged.append(line)
    for line in merged:
        if len(line) >= 3 and not re.fullmatch(r"[\d\s\-–/]+", line):
            add(line)
    for pat in CERT_PATTERNS:
        for m in pat.finditer(text):
            candidate = m.group(0)
            if not any(candidate.lower() in v.lower() for v in found.values()):
                add(candidate)
    return list(found.values())[:12]


_SKILL_NOISE = {"and", "etc", "others", "more", "various", "skills", "tools", "technologies", "languages", "frameworks",
                "databases", "cloud", "other", "basic", "advanced", "intermediate", "expert", "proficient", "good",
                "knowledge", "familiar", "concepts"}


def extract_candidate_skills(sections: dict[str, list[str]], text: str) -> list[str]:
    found = extract_skills(text)
    seen = {s.lower() for s in found}
    extras: list[str] = []
    for line in sections.get("skills", []):
        body = re.sub(r"^[A-Za-z &/]{3,30}:\s*", "", _strip_bullet(line))
        for tok in re.split(r"[,;|•]|\s{2,}|\s-\s", body):
            tok = tok.strip(" .()-")
            tok = re.sub(r"\s*\((?:advanced|intermediate|basic|expert|[\d.]+\s*y(?:ea)?rs?)\)$", "", tok, flags=re.I)
            if not (2 <= len(tok) <= 30) or len(tok.split()) > 3 or tok.lower() in _SKILL_NOISE:
                continue
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9+#.& \-]*", tok):
                continue
            canon = canonical_skill(tok)
            if canon.lower() in seen:
                continue
            if canon in CATEGORY or canon.lower() in AMBIGUOUS_PLAIN:
                found.append(canon)
            elif tok[0].isupper() or any(ch.isupper() for ch in tok[1:]):
                extras.append(tok)
            seen.add(canon.lower())
    return found + extras[:12]


def extract_profile(text: str, today: date | None = None) -> dict:
    lines = _lines(text)
    sections = split_sections(lines)
    warnings: list[str] = []

    email = extract_email(text)
    name = extract_name(lines, email)
    years, entries = extract_experience(sections, today)
    education, highest = extract_education(sections, lines)
    skills = extract_candidate_skills(sections, text)
    certs = extract_certifications(sections, text)

    if name == "Unknown Candidate":
        warnings.append("Could not detect the candidate's name.")
    if not email:
        warnings.append("No email address found - candidate cannot be contacted.")
    if not skills:
        warnings.append("No recognisable skills found.")
    if not entries and years == 0:
        warnings.append("No work-history dates found; experience treated as 0 years.")

    return {
        "name": name,
        "email": email,
        "phone": extract_phone(text),
        "headline": extract_headline(sections.get("header", []) or lines, name, entries),
        "links": extract_links(text),
        "skills": skills,
        "education": education,
        "highest_education": highest,
        "experience_years": years,
        "experience": entries,
        "certifications": certs,
        "warnings": warnings,
    }

