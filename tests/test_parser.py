import io

import pytest
from docx import Document

from app.exceptions import FileTooLargeError, ResumeParseError, UnsupportedFileTypeError
from app.services.parser import clean_text, parse_resume
from tests.conftest import resume_bytes


def test_parses_single_column_pdf():
    doc = parse_resume("aarav_mehta.pdf", resume_bytes("aarav_mehta.pdf"))
    assert doc.method == "pdf-text"
    assert "aarav.mehta@example.com" in doc.text
    assert "(cid:" not in doc.text


def test_two_column_pdf_is_not_interleaved():
    doc = parse_resume("sofia_alvarez.pdf", resume_bytes("sofia_alvarez.pdf"))
    assert doc.method == "pdf-columns"
    lines = doc.text.splitlines()
    assert lines[0] == "Sofia Alvarez"
    assert doc.text.index("SKILLS") < doc.text.index("EDUCATION") < doc.text.index("PROFILE") < doc.text.index("WORK EXPERIENCE")
    assert "SKILLS PROFILE" not in doc.text


def test_sidebar_pdf_with_header_beside_gutter():
    doc = parse_resume("hannah_lee.pdf", resume_bytes("hannah_lee.pdf"))
    assert doc.text.splitlines()[0] == "Hannah Lee"


def test_docx_table_layout_and_header_are_read():
    doc = parse_resume("priya_nair.docx", resume_bytes("priya_nair.docx"))
    assert doc.method == "docx"
    assert "Curriculum Vitae" in doc.text
    assert "PostgreSQL" in doc.text and "Flask" in doc.text


@pytest.mark.skipif(not __import__("shutil").which("tesseract"), reason="Tesseract not installed")
def test_scanned_pdf_falls_back_to_ocr():
    doc = parse_resume("nikhil_verma_scanned.pdf", resume_bytes("nikhil_verma_scanned.pdf"))
    assert doc.method == "pdf-ocr"
    assert doc.warnings
    assert "nikhil.verma@example.com" in doc.text


def test_rejects_unsupported_extension():
    with pytest.raises(UnsupportedFileTypeError):
        parse_resume("resume.txt", b"hello")


def test_rejects_empty_and_fake_files():
    with pytest.raises(ResumeParseError):
        parse_resume("a.pdf", b"")
    with pytest.raises(ResumeParseError):
        parse_resume("a.pdf", b"this is not a pdf")
    with pytest.raises(ResumeParseError):
        parse_resume("a.docx", b"this is not a docx")


def test_corrupted_files_give_friendly_errors():
    with pytest.raises(ResumeParseError):
        parse_resume("broken.pdf", b"%PDF-1.4 garbage garbage garbage")
    with pytest.raises(ResumeParseError):
        parse_resume("broken.docx", b"PK\x03\x04 not really a zip")


def test_docx_with_almost_no_text_is_rejected():
    buf = io.BytesIO()
    Document().save(buf)
    with pytest.raises(ResumeParseError):
        parse_resume("blank.docx", buf.getvalue())


def test_oversized_file_rejected(monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "max_upload_mb", 0)
    with pytest.raises(FileTooLargeError):
        parse_resume("aarav_mehta.pdf", resume_bytes("aarav_mehta.pdf"))


def test_clean_text_normalises_bullets_and_whitespace():
    assert clean_text("• Python   \u00a0 \n\n\n\n(cid:127) Java") == "- Python\n\n- Java"

