from app.services.skills import canonical_skill, extract_skills, related_skills, skill_category, text_mentions


def test_aliases_map_to_canonical_names():
    assert canonical_skill("postgres") == "PostgreSQL"
    assert canonical_skill("K8s") == "Kubernetes"
    assert canonical_skill("scikit learn") == "scikit-learn"
    assert canonical_skill("Something Unknown") == "Something Unknown"


def test_special_character_skills():
    found = extract_skills("Wrote C++ and C# services on ASP.NET, plus Node.js tooling and CI/CD.")
    assert {"C++", "C#", ".NET", "Node.js", "CI/CD"} <= set(found)


def test_java_is_not_found_inside_javascript():
    assert "Java" not in extract_skills("Experienced with JavaScript and TypeScript")
    assert "Java" in extract_skills("Experienced with Java and JavaScript")


def test_ambiguous_english_words_are_ignored_in_prose():
    found = extract_skills("Go to market, we excel at things, spring is here, ask the oracle.")
    assert found == []
    assert "Go" in extract_skills("Built services in Golang")


def test_related_skills_and_category():
    assert "PostgreSQL" in related_skills("MySQL")
    assert skill_category("Docker") == "Cloud & DevOps"
    assert skill_category("nonexistent-thing") == "Other"


def test_text_mentions_uses_word_boundaries():
    assert text_mentions("Java", "I write Java daily")
    assert not text_mentions("Java", "I write JavaScript daily")
    assert text_mentions("Tableau Prep", "used tableau prep for cleaning")

