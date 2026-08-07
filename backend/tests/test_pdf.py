"""
Tests for the PDF companion.

The PDF is derived from the canonical DOCX rather than rendered separately, so
the interesting question is not "does it look right" but **does the same text
arrive**. A conversion that silently drops the contact block, or reflows a
one-page Track B CV onto two, is worse than no PDF at all — the employer reads
a different document from the one that passed every check.

Skipped where LibreOffice cannot convert. That is not a hedge: a machine
without it must still produce a complete, sendable application, and these tests
would otherwise fail on exactly the configuration the design supports.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fixtures import PROFILE, full_cv, letter

from northbound.generate.render_docx import render_cover_letter, render_cv
from northbound.generate.render_pdf import (
    PdfUnavailable, converter_path, extract_pdf_text, page_count, pdf_available,
    render_pdf,
)

needs_pdf = pytest.mark.skipif(
    not pdf_available(), reason="LibreOffice cannot convert on this machine")


@pytest.fixture(scope="module")
def cv_pdf(tmp_path_factory) -> Path:
    d = tmp_path_factory.mktemp("pdf")
    return render_pdf(render_cv(full_cv(), PROFILE, d / "cv.docx"))


@needs_pdf
def test_the_six_recruiter_fields_survive_conversion(cv_pdf):
    """docs/07 F-C — the fields ~80% of the 7.4 seconds goes to."""
    text = extract_pdf_text(cv_pdf)
    c = PROFILE.contact_block
    cv = full_cv()

    for label, needle in [("name", c["name"]), ("email", c["email"]),
                          ("phone", c["phone"]), ("location", c["location"])]:
        assert needle in text, f"{label} lost in conversion: {needle!r}"

    for e in list(cv.experience) + list(cv.additional_experience):
        assert e.display_title in text, f"title lost: {e.display_title!r}"
        assert e.employer in text, f"employer lost: {e.employer!r}"
        assert e.dates in text, f"dates lost: {e.dates!r}"

    for ed in cv.education:
        assert ed.credential in text


@needs_pdf
def test_track_b_stays_one_page(cv_pdf):
    """docs/08 §1.5 — Track B is a one-page document, and reflow can break that."""
    assert page_count(cv_pdf) == 1, (
        f"{page_count(cv_pdf)} pages — conversion reflowed the layout")


@needs_pdf
def test_section_order_survives_conversion(cv_pdf):
    """docs/08 §2.4 — a farm employer must hit physical work first."""
    text = extract_pdf_text(cv_pdf)
    assert text.index("RELEVANT EXPERIENCE") < text.index("ADDITIONAL EXPERIENCE")
    assert text.index("Cumpsty Electrical") < text.index("Kurtosys Systems")


@needs_pdf
def test_the_icas_equivalency_survives(cv_pdf):
    """docs/08 §3.1 — most overseas applicants never state this."""
    text = extract_pdf_text(cv_pdf)
    assert "ICAS" in text and "24080341" in text


@needs_pdf
def test_no_day_level_dates_survive(cv_pdf):
    import re
    assert not re.search(
        r"\b\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\b",
        extract_pdf_text(cv_pdf))


@needs_pdf
def test_the_cover_letter_converts_too(tmp_path):
    docx = render_cover_letter(letter(), PROFILE, "Ridge Farms", tmp_path / "cl.docx")
    text = extract_pdf_text(render_pdf(docx))
    assert "Ridge Farms" in text
    assert "work permit" in text.lower(), "paragraph 4 must survive"
    assert PROFILE.contact_block["name"] in text


@needs_pdf
def test_concurrent_conversions_do_not_collide(tmp_path):
    """
    A batch converts many documents in one process. LibreOffice's default
    profile takes a lock, so a shared profile would serialise or fail — each
    conversion gets a throwaway one.
    """
    outs = [render_pdf(render_cv(full_cv(), PROFILE, tmp_path / f"cv{i}.docx"))
            for i in range(3)]
    assert len({p.name for p in outs}) == 3
    assert all(p.exists() and p.stat().st_size > 1000 for p in outs)


@needs_pdf
def test_dates_are_actually_right_aligned_on_the_page(cv_pdf):
    """
    The reader's-eye check: measure where the date ends up on the rendered page.

    Every other test in this repo reads the text layer, and the text layer is
    blind to position — a date at 1.7cm and a date at the margin extract
    identically. This one measures pixels, and it is the only test that would
    have caught the tab-stop bug from the side that matters: what an employer
    sees in the 7.4 seconds they spend on it.
    """
    import pdfplumber

    cv = full_cv()
    with pdfplumber.open(cv_pdf) as f:
        page = f.pages[0]
        right_margin_x = page.width - 48          # _configure sets 48pt margins
        words = page.extract_words()

        for entry in list(cv.experience) + list(cv.additional_experience):
            last = entry.dates.split()[-1]        # e.g. "2019" of "Oct 2017 – 2019"
            edges = [w["x1"] for w in words if w["text"] == last]
            assert edges, f"date {entry.dates!r} not found on the page"
            assert any(abs(x - right_margin_x) < 6 for x in edges), (
                f"date {entry.dates!r} ends at {max(edges):.0f}pt; the right "
                f"margin is {right_margin_x:.0f}pt — the column is not aligned")


# ---- the capability probe: the bug this file was written against ---------- #

def test_availability_is_probed_not_inferred_from_the_binary(monkeypatch):
    """
    `soffice` on PATH does not mean a PDF can be produced. A LibreOffice
    install without the Writer module — the configuration this was first
    written against — exits 0, prints "source file could not be loaded", and
    produces nothing. A presence check calls that available and the whole batch
    silently emits no PDFs.
    """
    import northbound.generate.render_pdf as rp

    monkeypatch.setattr(rp, "converter_path", lambda: "/usr/bin/soffice")
    monkeypatch.setattr(rp, "render_pdf", _raise_conversion_failure)
    assert rp.pdf_available(recheck=True) is False


def _raise_conversion_failure(*a, **k):
    raise RuntimeError("PDF conversion produced nothing (exit 0)")


def test_a_missing_converter_reports_unavailable_rather_than_raising(monkeypatch):
    import northbound.generate.render_pdf as rp

    monkeypatch.setattr(rp, "converter_path", lambda: None)
    assert rp.pdf_available(recheck=True) is False


def test_rendering_without_a_converter_raises_a_named_error(monkeypatch, tmp_path):
    """Callers must be able to tell 'not installed' from 'conversion broke'."""
    import northbound.generate.render_pdf as rp

    docx = render_cv(full_cv(), PROFILE, tmp_path / "cv.docx")
    monkeypatch.setattr(rp, "converter_path", lambda: None)
    with pytest.raises(PdfUnavailable, match="LibreOffice"):
        rp.render_pdf(docx)


def test_a_missing_source_file_is_a_file_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        render_pdf(tmp_path / "nope.docx")


@pytest.fixture(autouse=True)
def _restore_probe_cache():
    """Keep monkeypatched probes from poisoning the module-level cache."""
    import northbound.generate.render_pdf as rp
    saved = rp._CAPABILITY
    yield
    rp._CAPABILITY = saved


# ---- docs/08 §1.5: length is a rule only rendering can settle -------------- #

@needs_pdf
def test_an_over_long_track_b_cv_is_refused(tmp_path):
    """
    "Track B: 1 page, firmly. A farm or warehouse employer scanning fifty
    applications does not read page two."

    No character count predicts where a page breaks, so this can only be caught
    after rendering — which is exactly why it needs catching there rather than
    being left to chance.
    """
    from northbound.generate.generator import (
        GenerationOutcome, LayoutError, Posting, finalise,
    )
    from northbound.generate.schemas import Application, Bullet, ExperienceEntry

    long_cv = full_cv()
    padded = list(long_cv.experience)
    for i in range(6):
        padded.append(ExperienceEntry(
            role_id="gen.cumpsty",
            display_title=f"Electrician's Helper / Construction Labourer {i}",
            employer="Cumpsty Electrical",
            employer_context="residential estate electrical contractor, Paarl",
            location="Paarl, Western Cape, South Africa",
            dates=PROFILE.role("gen.cumpsty").display_dates,
            employment_type=None,
            bullets=[Bullet(text="Carried out wall chasing, trenching and "
                                 "excavation for cable and conduit runs on "
                                 "residential estate construction sites. " * 3,
                            evidence_id="gen.cumpsty.h2") for _ in range(4)]))
    long_cv.experience = padded

    posting = Posting(posting_id="x", title="general labourer - farm",
                      employer="Ridge Farms", body="body")
    outcome = GenerationOutcome(
        posting=posting, track="transferable", status="ready",
        application=Application(posting_id="x", posting_title="t",
                                employer="Ridge Farms", track="transferable",
                                cv=long_cv, letter=letter()))

    with pytest.raises(LayoutError, match="pages"):
        finalise(outcome, PROFILE, tmp_path)


@needs_pdf
def test_a_normal_track_b_cv_passes_the_length_gate(tmp_path):
    from northbound.generate.generator import GenerationOutcome, Posting, finalise
    from northbound.generate.schemas import Application

    posting = Posting(posting_id="x", title="general labourer - farm",
                      employer="Ridge Farms", body="body")
    outcome = GenerationOutcome(
        posting=posting, track="transferable", status="ready",
        application=Application(posting_id="x", posting_title="t",
                                employer="Ridge Farms", track="transferable",
                                cv=full_cv(), letter=letter()))
    paths = finalise(outcome, PROFILE, tmp_path)
    assert page_count(paths["cv_pdf"]) == 1
