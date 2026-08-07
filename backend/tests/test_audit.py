"""
Tests for the Layer 1 audit.

Each test encodes one rule from docs/04, /06, /07 or /08 as an executable fact.
The point is not coverage for its own sake: these are the rules whose failure
reaches a real employer, so each one gets a case that proves it blocks.
"""

from __future__ import annotations

import pytest
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


# --------------------------------------------------------------------------- #
# Education — the section that carried an evidence id and nothing else
# --------------------------------------------------------------------------- #

from northbound.generate.schemas import EducationEntry  # noqa: E402


def _edu(**over) -> EducationEntry:
    base = dict(
        evidence_id="edu.matric",
        credential="National Senior Certificate",
        institution="Noorder Paarl High School",
        year="2016",
        detail=("Assessed by ICAS as equivalent to Canadian Secondary School "
                "Graduation. File 24080341 IMM."),
    )
    base.update(over)
    return EducationEntry(**base)


def _with_edu(**over):
    return _app(cv=_cv(education=[_edu(**over)]))


def test_an_invented_graduation_year_blocks():
    """The matric is 2016. A wrong year is misrepresentation, not a typo."""
    res = audit(_with_edu(year="2018"), PROFILE)
    assert res.blocked and "education.year_mismatch" in _rules(res)


def test_an_invented_institution_blocks():
    res = audit(_with_edu(institution="Cape Town Technical College"), PROFILE)
    assert res.blocked and "education.institution_mismatch" in _rules(res)


def test_an_invented_credential_blocks():
    res = audit(_with_edu(credential="Bachelor of Computer Science"), PROFILE)
    assert res.blocked and "education.credential_mismatch" in _rules(res)


def test_a_shortened_credential_is_allowed():
    """The profile says 'National Senior Certificate (Matric)'; dropping the
    parenthetical is normal CV editing, not a different qualification."""
    res = audit(_with_edu(credential="National Senior Certificate"), PROFILE)
    assert "education.credential_mismatch" not in _rules(res)


def test_an_extended_institution_is_allowed():
    """docs/08 §3.2 — naming the country for a Canadian reader is expected."""
    res = audit(_with_edu(institution="Noorder Paarl High School, South Africa"),
                PROFILE)
    assert "education.institution_mismatch" not in _rules(res)


def test_either_year_of_a_study_range_is_allowed():
    """IT Academy ran 2020–2021; a CV may render either end or both."""
    for year in ("2020", "2021", "2020 – 2021"):
        res = audit(_app(cv=_cv(education=[_edu(
            evidence_id="edu.itacademy",
            credential="Certificate of IEP completion (Software Development programme)",
            institution="IT Academy",
            year=year, detail=None)])), PROFILE)
        assert "education.year_mismatch" not in _rules(res), year


def test_a_wrong_icas_file_number_blocks():
    """An officer can check this against ICAS's own records."""
    res = audit(_with_edu(detail=(
        "Assessed by ICAS as equivalent to Canadian Secondary School "
        "Graduation. File 99999999 IMM.")), PROFILE)
    assert res.blocked and "education.eca_file_number" in _rules(res)


def test_the_real_icas_file_number_passes():
    res = audit(_with_edu(), PROFILE)
    assert "education.eca_file_number" not in _rules(res)


def test_claiming_an_assessment_that_does_not_exist_blocks():
    """Only the matric has an ECA on record."""
    res = audit(_app(cv=_cv(education=[_edu(
        evidence_id="edu.shaw",
        credential="Professional Diploma in Web Development",
        institution="Shaw Academy", year="2019",
        detail="Assessed by ICAS as equivalent to a Canadian diploma.")])), PROFILE)
    assert res.blocked and "education.eca_invented" in _rules(res)


# --------------------------------------------------------------------------- #
# Skills and languages — the other two free-text sections
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("claim", [
    "forklift operation", "WHMIS certified", "welding (MIG/TIG)",
    "tractor operation", "pesticide application", "first aid",
    "class 1 licence", "food handler certificate",
])
def test_an_unheld_ticket_blocks(claim):
    """
    docs/08 §4 — an employer reads these as a qualification he holds and puts
    him on the machine. Claiming one he lacks is a statement they act on.
    """
    res = audit(_app(cv=_cv(skills={"Practical": [claim, "hand tools"]})), PROFILE)
    assert res.blocked and "skills.unheld_credential" in _rules(res), claim


def test_a_ticket_he_does_hold_is_allowed():
    """Fall-arrest work IS on record — the check must not block the real one."""
    res = audit(_app(cv=_cv(skills={
        "Practical": ["working at height with fall-arrest harness"]})), PROFILE)
    assert "skills.unheld_credential" not in _rules(res)


def test_an_unheld_ticket_in_the_cover_letter_blocks_too():
    """The bridge paragraph is exactly where the temptation lives."""
    res = audit(_app(letter=_letter(bridge=(
        "I have not worked on a farm, but I hold a valid forklift ticket and "
        "worked at height in Paarl for 18 months."))), PROFILE)
    assert res.blocked and "skills.unheld_credential" in _rules(res)


@pytest.mark.parametrize("bridge", [
    "I have not worked on a farm, but I am willing to complete WHMIS training "
    "before starting at Ridge Farms in Leamington.",
    "I do not hold a forklift ticket and would obtain one if required for the "
    "greenhouse work at Ridge Farms.",
])
def test_offering_to_obtain_a_ticket_is_allowed(bridge):
    """
    docs/08 §4 — stating willingness is honest and expected; it is the
    recommended bridge sentence. A rule that banned the vocabulary outright
    would block the correct document.
    """
    res = audit(_app(letter=_letter(bridge=bridge)), PROFILE)
    assert "skills.unheld_credential" not in _rules(res), bridge


def test_a_generic_descriptor_warns_rather_than_blocks():
    """
    Forcing a retry over "physical stamina" spends a generation on language
    that harms nobody. It still surfaces for a human.
    """
    res = audit(_app(cv=_cv(skills={"Practical": ["physical stamina"]})), PROFILE)
    assert not res.blocked
    assert "skills.thinly_grounded" in _rules(res)


def test_profile_skills_are_not_flagged_as_thin():
    res = audit(_app(cv=_cv(skills={
        "Practical": ["trenching and excavation", "hand tools", "wall chasing"],
        "Technical": ["React.js", "TypeScript"]})), PROFILE)
    assert "skills.thinly_grounded" not in _rules(res)


def test_an_invented_language_blocks():
    res = audit(_app(cv=_cv(languages=["English", "French", "Spanish"])), PROFILE)
    assert res.blocked and "languages.unknown" in _rules(res)


def test_the_five_recorded_languages_pass():
    res = audit(_app(cv=_cv(languages=[
        "French (native)", "English", "Lingala", "Kituba", "Afrikaans"])), PROFILE)
    assert "languages.unknown" not in _rules(res)
    assert "languages.overstated" not in _rules(res)


def test_claiming_a_non_native_language_as_native_blocks():
    """He speaks Afrikaans well. That is not the same claim."""
    res = audit(_app(cv=_cv(languages=["Afrikaans (native)"])), PROFILE)
    assert res.blocked and "languages.overstated" in _rules(res)


def test_referees_never_render():
    assert PROFILE.render_referees is False
    assert PROFILE.raw["referees"]["entries"] == []
