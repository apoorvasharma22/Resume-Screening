from datetime import date

from app.services.extractor import extract_email, extract_experience, extract_phone, extract_profile, split_sections
from tests.conftest import read_sample

TODAY = date(2026, 9, 21)


def profile(name):
    return extract_profile(read_sample(name), today=TODAY)


def test_full_profile_of_a_strong_backend_resume():
    p = profile("aarav_mehta.pdf")
    assert p["name"] == "Aarav Mehta"
    assert p["email"] == "aarav.mehta@example.com"
    assert p["phone"] == "+91 98765 43210"
    assert p["headline"] == "Senior Backend Engineer"
    assert p["highest_education"] == "master"
    assert 8.5 <= p["experience_years"] <= 9.5
    assert {"Python", "FastAPI", "PostgreSQL", "Kubernetes", "Terraform", "Kafka"} <= set(p["skills"])
    assert any("AWS Certified Solutions Architect" in c for c in p["certifications"])
    assert any("Kubernetes Administrator" in c for c in p["certifications"])
    assert p["warnings"] == []


def test_name_found_in_every_layout():
    names = {
        "sofia_alvarez.pdf": "Sofia Alvarez", "daniel_okafor.docx": "Daniel Okafor", "priya_nair.docx": "Priya Nair",
        "liam_chen.pdf": "Liam Chen", "meera_krishnan.pdf": "Meera Krishnan", "hannah_lee.pdf": "Hannah Lee",
        "carlos_rivera.pdf": "Carlos Rivera",
    }
    for file, expected in names.items():
        assert profile(file)["name"] == expected, file


def test_experience_uses_union_of_date_ranges_not_the_sum():
    sections = split_sections(["Experience", "Dev, A  2020 - 2022", "Dev, B  2021 - 2023", "Education", "BSc, Uni 2014 - 2018"])
    years, entries = extract_experience(sections, TODAY)
    assert years == 3.0
    assert len(entries) == 2


def test_present_and_numeric_month_ranges():
    sections = split_sections(["Experience", "Engineer  03/2025 - Present"])
    years, _ = extract_experience(sections, TODAY)
    assert 1.4 <= years <= 1.6


def test_explicit_years_statement_is_used_when_dates_are_missing():
    sections = split_sections(["Summary", "Seasoned engineer with 12+ years of professional experience."])
    years, _ = extract_experience(sections, TODAY)
    assert years == 12.0


def test_fresher_has_small_experience_and_degree():
    p = profile("hannah_lee.pdf")
    assert p["experience_years"] < 1
    assert p["highest_education"] == "bachelor"
    assert p["headline"] == "Software Engineering Graduate"


def test_education_entries_do_not_bleed_into_each_other():
    edu = profile("aarav_mehta.pdf")["education"]
    assert [e["level"] for e in edu] == ["master", "bachelor"]
    assert edu[0]["year"] == 2017 and edu[1]["year"] == 2015


def test_wrapped_certification_lines_are_stitched():
    certs = profile("ananya_iyer.pdf")["certifications"]
    assert "AWS Certified Machine Learning - Specialty" in certs


def test_wrapped_institution_names_are_stitched():
    edu = profile("ananya_iyer.pdf")["education"]
    assert edu[0]["institution"] == "International Institute of Information Technology Hyderabad"


def test_phone_ignores_date_ranges():
    assert extract_phone("Worked 2019 - 2021 at Acme\nCall +1 415 555 0142") == "+1 415 555 0142"
    assert extract_phone("no phone here 2019-2021") is None


def test_email_extraction():
    assert extract_email("Reach me: Jane.Doe+cv@Example.co.uk.") == "jane.doe+cv@example.co.uk"
    assert extract_email("nothing") is None


def test_name_falls_back_to_email_and_warns():
    p = extract_profile("skills: python, sql\n\ncontact jane.doe@example.com\n" + "x " * 30, today=TODAY)
    assert p["name"] == "Jane Doe"


def test_unrecognisable_text_yields_warnings_not_crashes():
    p = extract_profile("lorem ipsum dolor sit amet " * 10, today=TODAY)
    assert p["name"] == "Unknown Candidate"
    assert p["skills"] == [] and p["experience_years"] == 0
    assert len(p["warnings"]) >= 3


def test_unknown_skills_in_skills_section_are_kept():
    text = "Jane Roe\njane@example.com\nSkills\nPython, Snowpark, Great Expectations, Go\n"
    p = extract_profile(text, today=TODAY)
    assert "Go" in p["skills"] and "Snowpark" in p["skills"] and "Great Expectations" in p["skills"]

