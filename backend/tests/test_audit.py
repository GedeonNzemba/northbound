"""
Tests for the Layer 1 audit.

Each test encodes one rule from docs/04, /06, /07 or /08 as an executable fact.
The point is not coverage for its own sake: these are the rules whose failure
reaches a real employer, so each one gets a case that proves it blocks.
"""

from __future__ import annotations

from fixtures import PROFILE, app as _make_app, cv as _cv, letter as _letter

from northbound.generate.audit import audit
from northbound.generate.schemas import Bullet


def _app(cv=None, letter=None):
    return _make_app(cv_=cv, letter_=letter)


def _rules(res) -> set[str]:
    return {f.rule for f in res.findings}


# --------------------------------------------------------------------------- #

def test_clean_application_passes():
    res = audit(_app(), PROFILE)
    assert not res.blocked, res.report()


def test_unknown_evidence_id_blocks():
    cv = _cv(summary_evidence_ids=["gen.does.not.exist"])
    res = audit(_app(cv=cv), PROFILE)
    assert res.blocked and "evidence.unknown" in _rules(res)


def test_excluded_evidence_blocks():
    """gen.packer.h4 is verify: true — the unconfirmed recurrence claim."""
    cv = _cv(summary_evidence_ids=["gen.packer.h4"])
    res = audit(_app(cv=cv), PROFILE)
    assert res.blocked and "evidence.excluded" in _rules(res)


def test_work_permit_on_cv_blocks():
    """docs/08 §1.2 — the correction that matters most."""
    cv = _cv(summary="Seeking an LMIA-supported position; available to relocate.")
    res = audit(_app(cv=cv), PROFILE)
    assert res.blocked and "work_permit.on_cv" in _rules(res)


def test_missing_work_permit_paragraph_blocks():
    res = audit(_app(letter=_letter(authorisation="I look forward to hearing from you.")), PROFILE)
    assert res.blocked and "work_permit.missing" in _rules(res)


def test_offering_to_pay_lmia_blocks():
    """Recovering LMIA costs from a worker is illegal."""
    letter = _letter(authorisation=(
        "I would need an LMIA-supported permit and am happy to cover the LMIA fee myself."))
    res = audit(_app(letter=letter), PROFILE)
    assert res.blocked and "lmia.offer_to_pay" in _rules(res)


def test_invented_employment_type_blocks():
    """docs/06 — Cumpsty has no employment type and one must not be guessed."""
    cv = _cv()
    cv.experience[0].employment_type = "Full-time"
    res = audit(_app(cv=cv), PROFILE)
    assert res.blocked and "role.invented_employment_type" in _rules(res)


def test_date_mismatch_blocks():
    cv = _cv()
    cv.experience[0].dates = "Jan 2015 – Dec 2020"
    res = audit(_app(cv=cv), PROFILE)
    assert res.blocked and "role.date_mismatch" in _rules(res)


def test_day_level_date_blocks():
    """The painter conflict was resolved by month granularity."""
    cv = _cv()
    cv.experience[0].dates = "23 Nov 2016 – 5 Jan 2017"
    res = audit(_app(cv=cv), PROFILE)
    assert res.blocked and {"dates.day_level", "role.date_mismatch"} & _rules(res)


def test_ai_generic_phrase_blocks():
    """docs/07 F-D — genericness is what gets rejected."""
    letter = _letter(opening=(
        "I am writing to express my interest in the farm role at Ridge Farms in "
        "Leamington, Ontario."))
    res = audit(_app(letter=letter), PROFILE)
    assert res.blocked and "banned.generic" in _rules(res)


def test_fabrication_phrase_blocks():
    letter = _letter(bridge=(
        "I have extensive experience in commercial agriculture across Paarl and "
        "Cape Town over 18 months."))
    res = audit(_app(letter=letter), PROFILE)
    assert res.blocked and "banned.fabrication" in _rules(res)


def test_thin_paragraph_blocks_on_specificity():
    letter = _letter(bridge="I am a hard worker and I learn quickly.")
    res = audit(_app(letter=letter), PROFILE)
    assert res.blocked and "specificity.thin" in _rules(res)


def test_us_spelling_blocks():
    cv = _cv(skills={"Practical": ["color matching", "hand tools"]})
    res = audit(_app(cv=cv), PROFILE)
    assert res.blocked and "language.us_spelling" in _rules(res)


def test_prohibited_personal_information_blocks():
    cv = _cv(summary="Date of birth: 24 September 1998. Physical worker.")
    res = audit(_app(cv=cv), PROFILE)
    assert res.blocked and "prohibited.personal" in _rules(res)


def test_software_in_primary_experience_blocks_on_track_b():
    """docs/08 §2.4 — software belongs under Additional Experience on Track B."""
    cv = _cv()
    cv.experience[0].bullets.append(
        Bullet(text="Built React components for the platform.", evidence_id="exp.kurtosys.h1"))
    res = audit(_app(cv=cv), PROFILE)
    assert res.blocked and "track_b.software_above_fold" in _rules(res)


def test_unanswered_screening_questions_block():
    letter = _letter(screening_answers=[])
    res = audit(_app(letter=letter), PROFILE,
                posting_text="Are you available for shift or on-call work?")
    assert res.blocked and "screening.unanswered" in _rules(res)


def test_missing_employer_context_warns_but_does_not_block():
    cv = _cv()
    cv.experience[0].employer_context = None
    res = audit(_app(cv=cv), PROFILE)
    assert "context.missing" in _rules(res)
    assert not res.blocked, "a missing context clause should warn, not block"


def test_referees_never_render():
    assert PROFILE.render_referees is False
    assert PROFILE.raw["referees"]["entries"] == []
