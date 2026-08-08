"""
The first live batch, turned into tests.

Twenty postings went through the engine with real money. Eight came back parked
with 28 findings between them, and reading the documents showed that roughly
twenty of those findings were the engine's fault, not the writing's — four rules
firing on sentences that were exactly what docs/06 and docs/08 ask for.

Every test below quotes a real sentence from `backend/out/parked/`. They are
kept verbatim, typos of the model's own included, because paraphrasing them
would test a rule against text the rule has never actually seen. Each one is a
document that should have been sent and was not.

The counterpart cases — the sentences that SHOULD block — sit beside them.
Loosening a rule until the false positives stop is easy and useless; the pairs
are what stop that.
"""

from __future__ import annotations

from fixtures import PROFILE, app as _make_app, cv as _cv, letter as _letter

from northbound.generate.audit import audit


def _rules(res) -> set[str]:
    return {f.rule for f in res.findings}


def _blocks(res, rule: str) -> bool:
    return any(f.rule == rule and f.severity == "block" for f in res.findings)


# --------------------------------------------------------------------------- #
# skills.unheld_credential — 6 of 28 findings, all on honest sentences
# --------------------------------------------------------------------------- #

MUCCI_BRIDGE = (
    "I want to be straight with you: I have not worked in a greenhouse, and I "
    "have not hand-harvested cucumbers or tomatoes. Your posting says no "
    "experience and that you will train; I will take that training exactly as "
    "given, including any WHMIS or workplace safety course Mucci Farms "
    "requires, and I will arrange my own transportation to the Seacliff Drive "
    "site."
)

CANWEST_BRIDGE = (
    "I should be straight with you about what I have not done. I have not "
    "supervised a harvest crew, I have not operated or maintained farm "
    "machinery such as a tractor, and I have not hoed between rows on a "
    "commercial vegetable field. What I have done is take direction on an "
    "active building site for eighteen months."
)

GLASS_GROW_AVAILABILITY = (
    "Available to start as soon as possible and to relocate to Kingsville, "
    "Ontario. Able to work morning, day, evening and weekend shifts, overtime, "
    "and 30 to 70 hours per week. I hold no farm safety, WHMIS or first aid "
    "certificate and am willing to complete whatever training the farm requires."
)

GLASS_GROW_BRIDGE = (
    "Your posting says no experience and that you will train — I would take "
    "that training exactly as given, including the tomato work, the grading "
    "standards and any farm safety, WHMIS or first aid course you require, "
    "none of which I currently hold."
)


def test_will_take_that_training_is_not_a_credential_claim():
    """
    Mucci Farms. The rule matched "would take" but not "will take", so it
    blocked the one sentence docs/08 §4 explicitly asks for.
    """
    res = audit(_make_app(letter_=_letter(bridge=MUCCI_BRIDGE)), PROFILE)
    assert not _blocks(res, "skills.unheld_credential"), res.report()


def test_an_outright_denial_is_not_a_credential_claim():
    """
    Canwest Farms. "I have not operated ... such as a tractor" was read as a
    claim to operate tractors, because the rule looked for willingness language
    and a denial is not willingness.
    """
    res = audit(_make_app(letter_=_letter(bridge=CANWEST_BRIDGE)), PROFILE)
    assert not _blocks(res, "skills.unheld_credential"), res.report()


def test_hold_no_certificate_is_not_a_claim_to_hold_one():
    """
    Glass Grow Farms, on the CV. "I hold no ... WHMIS or first aid certificate"
    tripped the held-claim pattern on the word "hold": the guard was a `(?<!not )`
    lookbehind, and here the negation comes AFTER the verb.
    """
    res = audit(_make_app(cv_=_cv(availability=GLASS_GROW_AVAILABILITY)), PROFILE)
    assert not _blocks(res, "skills.unheld_credential"), res.report()


def test_none_of_which_i_currently_hold_is_not_a_claim():
    """Glass Grow Farms, in the letter. Same verb, negated from four words away."""
    res = audit(_make_app(letter_=_letter(bridge=GLASS_GROW_BRIDGE)), PROFILE)
    assert not _blocks(res, "skills.unheld_credential"), res.report()


def test_a_real_credential_claim_still_blocks():
    """The pair that keeps the loosening honest."""
    res = audit(_make_app(letter_=_letter(
        bridge="I have not worked on a farm, but I hold a valid forklift "
               "ticket and a current first aid certificate.")), PROFILE)
    assert _blocks(res, "skills.unheld_credential"), res.report()


def test_a_denial_elsewhere_does_not_launder_a_held_claim():
    """
    A denial in the same paragraph must not buy a claim in the next sentence.
    This is the failure mode the original lookbehind existed to prevent, and it
    has to survive every relaxation above.
    """
    res = audit(_make_app(letter_=_letter(
        bridge="I have never operated a tractor and I have not worked a "
               "harvest. I am certified in fall-arrest systems and hold my "
               "WHMIS.")), PROFILE)
    assert _blocks(res, "skills.unheld_credential"), res.report()


# --------------------------------------------------------------------------- #
# d1.coursework_as_certification — the rule blocked its own required disclaimer
# --------------------------------------------------------------------------- #

GLASS_GROW_EDUCATION_DETAIL = (
    "Remote / distance learning. Coursework only (not held certifications): "
    "cloud (AWS, Microsoft Azure), .NET and C#, Java, Python, SQL Server, "
    "HTML5/JavaScript/CSS3, mobile development and software testing."
)


def test_the_d1_disclaimer_is_not_itself_a_d1_violation():
    """
    Glass Grow Farms, twice — on 'Python' and on 'HTML5'.

    The rule searched for a coursework name within 90 characters of any
    certification word. The word here is inside "not held certifications", which
    is the exact rendering docs/06 D1 requires. Proximity could not see that.
    """
    from northbound.generate.schemas import EducationEntry

    cv = _cv(education=[EducationEntry(
        evidence_id="edu.itacademy",
        credential="Certificate of IEP completion (Software Development programme)",
        institution="IT Academy (a division of IT SA Computer Services & Solutions (Pty) Ltd)",
        year="2021",
        detail=GLASS_GROW_EDUCATION_DETAIL,
    )])
    res = audit(_make_app(cv_=cv), PROFILE)
    assert not _blocks(res, "d1.coursework_as_certification"), res.report()


def test_a_bare_technology_name_in_a_skills_list_is_not_a_certification():
    """'Python' is a coursework item AND an ordinary skill. Listing it is fine."""
    cv = _cv(skills={"Technical": ["Python", "HTML5", "JavaScript"]})
    res = audit(_make_app(cv_=cv), PROFILE)
    assert not _blocks(res, "d1.coursework_as_certification"), res.report()


def test_coursework_written_as_a_held_certification_still_blocks():
    res = audit(_make_app(cv_=_cv(
        summary="Certified in Python and holding AZ-900, applying for farm work.")),
        PROFILE)
    assert _blocks(res, "d1.coursework_as_certification"), res.report()


def test_the_dash_in_a_coursework_name_does_not_decide_whether_the_rule_applies():
    """
    The profile writes "AWS Certified Developer – Associate" with an en dash. A
    CV may write a hyphen or an em dash, and an exact-bytes match would fail
    open — the rule silently stops applying, which is the worst way to fail.
    """
    for dash in ("-", "–", "—"):
        cv = _cv(summary=f"AWS Certified Developer {dash} Associate certification, "
                         f"awarded 2021. Applying for farm work.")
        res = audit(_make_app(cv_=cv), PROFILE)
        assert _blocks(res, "d1.coursework_as_certification"), f"{dash!r}: {res.report()}"


def test_a_bare_exam_code_written_as_held_blocks():
    """A CV cites "AZ-900", not "AZ-900 Microsoft Azure Fundamentals"."""
    res = audit(_make_app(cv_=_cv(
        summary="Holds AZ-900 and 1Z0-808. Applying for greenhouse work.")), PROFILE)
    assert _blocks(res, "d1.coursework_as_certification"), res.report()


def test_coursework_under_a_certifications_heading_blocks():
    """
    The structural version. A group headed "Certifications" makes every item
    under it a claimed credential, and no sentence-level grammar would show it.
    """
    cv = _cv(skills={"Certifications": ["Python", "HTML5"]})
    res = audit(_make_app(cv_=cv), PROFILE)
    assert _blocks(res, "d1.coursework_as_certification"), res.report()


# --------------------------------------------------------------------------- #
# output.incomplete — VENERICA MEATS produced five findings that all meant
# "the model wrote nothing"
# --------------------------------------------------------------------------- #

def test_an_empty_letter_reports_the_generation_failure_not_its_symptoms():
    """
    Every paragraph came back blank. The audit reported three thin-paragraph
    blocks, a missing work-permit paragraph and unanswered screening questions —
    five findings, none of which a repair turn could act on, and none of which
    said the fields were empty.
    """
    letter = _letter(opening="", evidence="", bridge="", authorisation="")
    res = audit(_make_app(letter_=letter), PROFILE)

    assert _blocks(res, "output.incomplete"), res.report()
    assert _rules(res) == {"output.incomplete"}, (
        "an empty document must not also be reported as a badly written one")
    message = next(f.message for f in res.findings)
    for field in ("letter.opening", "letter.evidence", "letter.bridge",
                  "letter.authorisation"):
        assert field in message, f"{field} must be named so the retry can act on it"


def test_a_written_but_generic_paragraph_is_still_judged_on_specificity():
    """The completeness gate must not swallow the rules it runs in front of."""
    letter = _letter(bridge="I am a hard worker and I learn quickly, and I "
                            "would be a good addition to any team anywhere.")
    res = audit(_make_app(letter_=letter), PROFILE)
    assert _blocks(res, "specificity.thin"), res.report()
    assert not _blocks(res, "output.incomplete"), res.report()
