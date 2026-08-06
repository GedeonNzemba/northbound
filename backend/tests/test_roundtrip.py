"""
Layer 2 tests — the ATS round-trip.

These prove the renderer produces documents an ATS can actually read. The
negative tests matter as much as the positive one: they prove the check would
catch a regression rather than passing everything.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from docx import Document

from northbound.evaluate.ats_roundtrip import (
    extract_via_docx, extract_via_xml, roundtrip,
)
from northbound.generate.render_docx import render_cv
from northbound.generate.schemas import (
    Bullet, EducationEntry, ExperienceEntry, GeneratedCV,
)
from northbound.profile import load_profile

PROFILE = load_profile()


def _track_b_cv() -> GeneratedCV:
    return GeneratedCV(
        track="transferable",
        target_noc="85101",
        headline="General Farm Worker",
        summary=("Physical worker with 18 months on estate construction sites in "
                 "Paarl and a year in kitchen and food production."),
        summary_evidence_ids=["gen.cumpsty.h1"],
        skills={"Practical": ["working at height with fall-arrest harness",
                              "hand tools", "trenching and excavation"]},
        experience=[
            ExperienceEntry(
                role_id="gen.cumpsty",
                display_title="Electrician's Helper / Construction Labourer (NOC 75110)",
                employer="Cumpsty Electrical",
                employer_context="residential estate electrical contractor, Paarl",
                location="Paarl, Western Cape, South Africa",
                dates=PROFILE.role("gen.cumpsty").display_dates,
                employment_type=None,
                bullets=[
                    Bullet(text="Assisted qualified electricians on residential estate "
                                "construction sites, including Val de Vie Estate.",
                           evidence_id="gen.cumpsty.h1"),
                    Bullet(text="Carried out wall chasing, trenching and excavation for "
                                "cable and conduit runs.",
                           evidence_id="gen.cumpsty.h2"),
                ],
            ),
            ExperienceEntry(
                role_id="gen.mcdonalds",
                display_title="Food Service / Kitchen Helper (NOC 65201)",
                employer="McDonald's",
                employer_context="quick-service restaurant",
                location="South Africa",
                dates=PROFILE.role("gen.mcdonalds").display_dates,
                employment_type=None,
                bullets=[Bullet(
                    text="Prepared food to standardised procedures under time pressure.",
                    evidence_id="gen.mcdonalds.h1")],
            ),
        ],
        additional_experience=[ExperienceEntry(
            role_id="exp.kurtosys",
            display_title="Front-End Developer (NOC 21234)",
            employer="Kurtosys Systems",
            employer_context="FinTech / asset-management technology",
            location="Cape Town, South Africa",
            dates=PROFILE.role("exp.kurtosys").display_dates,
            employment_type="Full-time",
            bullets=[Bullet(
                text="Built and maintained financial websites for international clients.",
                evidence_id="exp.kurtosys.h1")],
        )],
        education=[EducationEntry(
            evidence_id="edu.matric",
            credential="National Senior Certificate",
            institution="Noorder Paarl High School, South Africa",
            year="2016",
            detail=("Assessed by ICAS (International Credential Assessment Service of "
                    "Canada) as equivalent to Canadian Secondary School Graduation. "
                    "File 24080341 IMM, March 2025."),
        )],
        languages=["French (native)", "English", "Lingala", "Kituba", "Afrikaans"],
        availability="Available to relocate; can start on your timeline.",
    )


@pytest.fixture(scope="module")
def rendered(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("cv") / "cv.docx"
    return render_cv(_track_b_cv(), PROFILE, out)


def test_roundtrip_passes(rendered):
    res = roundtrip(rendered, _track_b_cv(), PROFILE)
    assert res.passed, res.report()


def test_all_six_recruiter_fields_recovered(rendered):
    """docs/07 F-C — the fields ~80% of the 7.4 seconds goes to."""
    res = roundtrip(rendered, _track_b_cv(), PROFILE)
    for key, ok in res.recovered.items():
        assert ok, f"{key} was not recoverable: {res.missing_detail.get(key)}"


def test_both_extraction_paths_agree(rendered):
    """A pass must not depend on one library's behaviour."""
    a, b = extract_via_docx(rendered), extract_via_xml(rendered)
    for needle in ("Gedeon Christ Nzemba", "gedeon@gedeonchrist.com",
                   "Cumpsty Electrical", "Val de Vie"):
        assert needle in a, f"{needle!r} missing from python-docx extraction"
        assert needle in b, f"{needle!r} missing from raw XML extraction"


def test_no_structural_hazards(rendered):
    """No tables, images, headers, footers, text boxes or columns."""
    res = roundtrip(rendered, _track_b_cv(), PROFILE)
    assert res.structural == [], res.structural


def test_contact_block_is_body_text_not_header(rendered):
    """
    docs/08 §1.3 — the single most damaging layout mistake. Contact details in
    a header are invisible to many parsers and the application arrives anonymous.
    """
    doc = Document(str(rendered))
    body = "\n".join(p.text for p in doc.paragraphs)
    assert "Gedeon Christ Nzemba" in body
    assert "gedeon@gedeonchrist.com" in body
    import zipfile
    with zipfile.ZipFile(rendered) as z:
        assert not [n for n in z.namelist() if n.startswith("word/header")]


def test_no_street_address_or_postal_code(rendered):
    """docs/08 §1.3 — city + country only."""
    text = extract_via_xml(rendered)
    import re
    assert not re.search(r"\b\d+\s+[A-Z][a-z]+\s+(Road|Street|Drive|Flat)\b", text)
    assert not re.search(r"\b[A-Z]\d[A-Z]\s?\d[A-Z]\d\b", text)


def test_no_day_level_dates(rendered):
    """The painter/packer resolution must survive rendering."""
    import re
    text = extract_via_xml(rendered)
    assert not re.search(
        r"\b\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\b",
        text), "day-level date survived into the rendered document"


def test_track_b_puts_software_below_relevant_experience(rendered):
    """docs/08 §2.4 — a farm employer must hit physical work first."""
    text = extract_via_docx(rendered)
    assert text.index("RELEVANT EXPERIENCE") < text.index("ADDITIONAL EXPERIENCE")
    assert text.index("Cumpsty Electrical") < text.index("Kurtosys Systems")


def test_icas_equivalency_survives_rendering(rendered):
    """docs/08 §3.1 — most overseas applicants never state this."""
    text = extract_via_xml(rendered)
    assert "ICAS" in text and "equivalent to Canadian Secondary School Graduation" in text
    assert "24080341" in text


# ---- negative tests: prove the check would catch a regression ------------- #

def test_roundtrip_detects_a_table(tmp_path):
    doc = Document()
    doc.add_paragraph("Gedeon Christ Nzemba")
    doc.add_table(rows=1, cols=2)
    p = tmp_path / "bad.docx"
    doc.save(str(p))
    res = roundtrip(p, _track_b_cv(), PROFILE)
    assert not res.passed
    assert any("table" in s for s in res.structural)


def test_roundtrip_detects_contact_details_in_a_header(tmp_path):
    doc = Document()
    doc.sections[0].header.paragraphs[0].text = "Gedeon Christ Nzemba | gedeon@gedeonchrist.com"
    doc.add_paragraph("Work Experience")
    p = tmp_path / "header.docx"
    doc.save(str(p))
    res = roundtrip(p, _track_b_cv(), PROFILE)
    assert not res.passed
    assert any("header" in s for s in res.structural)
    assert res.recovered["name"] is False, "name in a header must count as lost"
