"""
Layer 1 — deterministic checks. docs/07, extended by docs/08 §6.

Cheap, instant, and they BLOCK. Nothing here is advisory: a document that fails
any of these is not sent, however good it reads.

The order matters. Truth checks run first, because a beautifully formatted lie is
worse than an ugly honest document.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Literal

from ..profile import Profile
from .schemas import Application, CoverLetter, GeneratedCV

Severity = Literal["block", "warn"]


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: Severity
    message: str
    where: str = ""

    def __str__(self) -> str:
        loc = f" [{self.where}]" if self.where else ""
        return f"{self.severity.upper():5} {self.rule}{loc}: {self.message}"


@dataclass
class AuditResult:
    findings: list[Finding] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return any(f.severity == "block" for f in self.findings)

    @property
    def blocks(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "block"]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "warn"]

    def report(self) -> str:
        if not self.findings:
            return "PASS — no findings"
        head = "BLOCKED" if self.blocked else "PASS (with warnings)"
        return head + "\n" + "\n".join(f"  {f}" for f in self.findings)


# --------------------------------------------------------------------------- #
# Rule data
# --------------------------------------------------------------------------- #

# docs/04 — fabricated-competence tells.
BANNED_FABRICATION = [
    r"\bextensive experience in\b", r"\bexpert in\b", r"\bfully certified\b",
    r"\bproven track record in\b", r"\bessentially the same as\b",
    r"\byears of experience in\b",
]

# "equivalent to" is BANNED as a competence claim ("my coding is equivalent to
# trade experience") but REQUIRED in the credential-assessment line, which
# docs/08 §3.1 mandates verbatim: "assessed by ICAS as equivalent to Canadian
# Secondary School Graduation". Distinguish by context, not by the phrase.
CREDENTIAL_EQUIVALENCY_CONTEXT = re.compile(
    r"(assessed by|evaluation|ICAS|WES|IQAS|ICES|credential)", re.I)

# docs/07 F-D — AI-genericness tells. Genericness is the risk, not AI.
BANNED_GENERIC = [
    r"\bI am writing to express my interest\b", r"\bI am excited to apply\b",
    r"\bI believe I would be a great fit\b", r"\bIn today's fast-paced\b",
    r"\bI am confident that my skills\b", r"\bleverage\b", r"\bproven ability to\b",
    r"\bseamlessly\b", r"\bcutting-edge\b", r"\bdynamic\b", r"\bpassionate about\b",
    r"\btrack record of success\b", r"\bhit the ground running\b",
    r"\bwealth of experience\b", r"\bthink outside the box\b",
]

# docs/08 §1.1 — must never appear anywhere.
#
# Every pattern here has to be specific enough that ordinary CV vocabulary
# cannot trip it. "single" was originally in the marital-status list and blocked
# every Track A CV that mentioned single-page applications — a false positive
# that costs a generation and hands the model a retry note it cannot act on.
# "marital status" as a label already catches the real case, so the bare word is
# gone; "married"/"divorced"/"widowed" have no other CV use and stay.
PROHIBITED_PERSONAL = {
    "date of birth": r"\b(date of birth|d\.?o\.?b\.?)\b",
    "age": r"\b(?:I am |aged )\d{2} years old\b",
    "marital status": r"\bmarital status\b|\b(married|divorced|widowed)\b",
    "nationality": r"\b(nationality|citizenship)\s*[:=]",
    "gender": r"\b(gender|sex)\s*[:=]",
    # Case-sensitive for the acronym: the whole blob is searched with re.I, and
    # a lowercase "sin" is an ordinary English word.
    "SIN": r"\bsocial insurance number\b|(?-i:\bSIN\b)",
    "photo": r"\b(photograph attached|photo attached)\b",
    "religion": r"\breligion\s*[:=]",
    "references-on-cv": r"\breferences (are )?available (up)?on request\b",
    "salary expectation": r"\b(salary expectation|expected salary|current salary)\b",
}

# docs/08 §1.2 — belongs in the cover letter ONLY.
WORK_PERMIT_TERMS = r"\b(work permit|LMIA|visa sponsorship|sponsorship|work authorisation|work authorization|open permit|closed permit)\b"

# docs/08 §1.4 — Canadian English, which is neither American nor British.
#
# It takes the British -our and -re endings and the doubled consonant, and the
# AMERICAN -ize/-yze endings: the Government of Canada's own editorial style
# follows American practice for -ize and -yze, and "program" is the Canadian
# form, not "programme".
#
# This table used to say the reverse. It blocked "organization", "recognize",
# "analyze" and "program" — every one of them the correct Canadian spelling —
# and it carried the entry `"enrolled ": "enrolled "`, which flagged a correct
# word and instructed the writer to replace it with itself. That fired on a
# real document in the first live batch, on the sentence "I am not enrolled in
# any studies now."
#
# Genuinely contested forms are deliberately absent. "fulfil"/"fulfill" and
# "catalogue"/"catalog" are both current in Canada, and a BLOCK on a word
# Canadians write both ways costs a generation and teaches the model nothing.
NON_CANADIAN_SPELLINGS = {
    # American -or / -er, where Canada keeps the British form.
    "color": "colour", "behavior": "behaviour", "favorite": "favourite",
    "honor": "honour", "labor": "labour", "neighbor": "neighbour",
    "center": "centre", "theater": "theatre", "fiber": "fibre",
    # American -se, where Canada keeps the -ce noun.
    "defense": "defence", "offense": "offence",
    # American single consonant, where Canada doubles before a suffix.
    "traveled": "travelled", "traveling": "travelling",
    "canceled": "cancelled", "canceling": "cancelling",
    "modeling": "modelling", "labeled": "labelled", "fueled": "fuelled",
    # British -ise / -yse / -gramme, where Canada takes the American form.
    # Gedeon writes South African English, which is British here, so this half
    # of the table is the one that will actually fire.
    "organisation": "organization", "organise": "organize",
    "organised": "organized", "organising": "organizing",
    "recognise": "recognize", "recognised": "recognized",
    "analyse": "analyze", "analysed": "analyzed",
    "specialise": "specialize", "specialised": "specialized",
    "prioritise": "prioritize", "standardise": "standardize",
    "programme": "program", "programmes": "programs",
}

# Correct in one part of speech and wrong in another, so a block would be a coin
# toss. Canada uses the -ce noun and the -se verb: a driver's licence, but to
# license a vendor. Worth a human glance, never worth a retry.
AMBIGUOUS_SPELLINGS = {
    "license": "licence — Canada spells the NOUN -ce (a driver's licence) and "
               "the verb -se (to license a vendor)",
}

# docs/08 §2.1 — parsers pattern-match on these.
PERMITTED_HEADINGS = {
    "professional summary", "summary", "work experience", "experience",
    "employment history", "relevant experience", "additional experience",
    "education", "education & training", "education and training",
    "skills", "technical skills", "certifications",
    "licences and certifications", "languages", "projects", "awards",
    "availability", "portfolio",
}

DAY_LEVEL_DATE = re.compile(r"\b\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\b")
BARE_MONTH_ABBR_INCONSISTENT = re.compile(r"\bSept\b")


# --------------------------------------------------------------------------- #
# The audit
# --------------------------------------------------------------------------- #

def audit(app: Application, profile: Profile, *, posting_text: str = "") -> AuditResult:
    r = AuditResult()
    cv, letter = app.cv, app.letter

    # Nothing downstream means anything on an empty document, and running the
    # rest would bury the real problem under a pile of derived findings. On the
    # first live batch a letter came back with all four paragraphs blank and was
    # reported as "0 concrete particulars" three times over, plus a missing
    # work-permit paragraph and unanswered screening questions — five findings
    # that all say "the model wrote nothing" in a way no retry could act on.
    if _check_completeness(cv, letter, r):
        return r

    _check_evidence(cv, letter, profile, r)
    _check_education(cv, profile, r)
    _check_skill_claims(cv, letter, profile, r)
    _check_languages(cv, profile, r)
    _check_standing_instructions(cv, letter, profile, r)
    _check_prohibited_content(cv, letter, r)
    _check_work_permit_placement(cv, letter, r)
    _check_banned_phrases(cv, letter, r)
    _check_structure(cv, r)
    _check_dates(cv, r)
    _check_canadian_english(cv, letter, r)
    _check_specificity(letter, r)
    _check_screening_questions(letter, posting_text, r)
    _check_units(cv, letter, posting_text, r)
    _check_employer_context(cv, r)
    return r


# ---- did the model actually write anything -------------------------------- #

# Below this, a field is blank or a stub rather than prose. Deliberately low:
# the job is to separate "wrote nothing" from "wrote badly", and the rules that
# judge badly-written text are the ones that should get to speak. Every other
# check in this file assumes there is something to check.
MIN_PARAGRAPH_CHARS = 25


def _check_completeness(cv: GeneratedCV, letter: CoverLetter,
                        r: AuditResult) -> bool:
    """
    Every required field carries text. Returns True if the document is a shell.

    This is a generation failure, not a document failure, and it is reported as
    one — with the field names — so the repair turn is told the one thing it can
    act on rather than a set of consequences.
    """
    empty = [name for name, text in (
        ("letter.opening", letter.opening),
        ("letter.evidence", letter.evidence),
        ("letter.bridge", letter.bridge),
        ("letter.authorisation", letter.authorisation),
        ("cv.summary", cv.summary),
    ) if len(" ".join((text or "").split())) < MIN_PARAGRAPH_CHARS]

    if not cv.experience:
        empty.append("cv.experience (no roles at all)")

    if not empty:
        return False

    r.findings.append(Finding(
        "output.incomplete", "block",
        "the model returned a document with empty required fields: "
        + ", ".join(empty)
        + ". Write the full text of each — this is not a content rule, the "
          "fields are literally blank"))
    return True


# ---- truth ---------------------------------------------------------------- #

def _all_cited_ids(cv: GeneratedCV, letter: CoverLetter) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    out += [(i, "cv.summary") for i in cv.summary_evidence_ids]
    for e in list(cv.experience) + list(cv.additional_experience):
        out += [(i, f"cv.experience[{e.role_id}]")
                for b in e.bullets for i in b.evidence_ids]
    out += [(e.evidence_id, "cv.education") for e in cv.education]
    out += [(i, "cv.portfolio") for i in cv.portfolio_ids]
    out += [(i, "letter.evidence") for i in letter.evidence_ids]
    out += [(i, "letter.bridge") for i in letter.bridge_evidence_ids]
    return out


def _check_evidence(cv, letter, profile: Profile, r: AuditResult) -> None:
    """docs/04 Rules 1-2. Every claim traces to a usable profile entry."""
    for ev_id, where in _all_cited_ids(cv, letter):
        ev = profile.evidence.get(ev_id)
        if ev is None:
            r.findings.append(Finding(
                "evidence.unknown", "block",
                f"cites '{ev_id}', which does not exist in master-profile.yaml", where))
        elif not ev.usable:
            r.findings.append(Finding(
                "evidence.excluded", "block",
                f"cites '{ev_id}', excluded ({ev.exclusion_reason})", where))

    for e in list(cv.experience) + list(cv.additional_experience):
        try:
            role = profile.role(e.role_id)
        except KeyError:
            r.findings.append(Finding(
                "role.unknown", "block", f"unknown role_id '{e.role_id}'", "cv.experience"))
            continue
        if role.excluded:
            r.findings.append(Finding(
                "role.excluded", "block",
                f"role '{e.role_id}' is excluded ({role.exclusion_reason})", "cv.experience"))
        if e.employer.strip() and role.employer and e.employer.strip() not in role.employer:
            r.findings.append(Finding(
                "role.employer_mismatch", "block",
                f"rendered employer {e.employer!r} does not match profile {role.employer!r}",
                e.role_id))
        if e.dates != role.display_dates:
            r.findings.append(Finding(
                "role.date_mismatch", "block",
                f"rendered dates {e.dates!r} != profile {role.display_dates!r}", e.role_id))
        # docs/06 — a guessed employment type is a false statement.
        if role.employment_type is None and e.employment_type:
            r.findings.append(Finding(
                "role.invented_employment_type", "block",
                f"employment_type {e.employment_type!r} invented — profile has none "
                "and one must not be guessed", e.role_id))


# The D1 rule — IT Academy items are coursework, never held credentials — used
# to fire whenever a coursework name appeared within 90 characters of any
# certification word. On the first live batch that blocked this line:
#
#   "Coursework only (not held certifications): cloud (AWS, Microsoft Azure),
#    .NET and C#, Java, Python, SQL Server, HTML5/JavaScript/CSS3 …"
#
# which is precisely the compliant rendering docs/06 D1 demands. The word
# "certifications" was inside the window; that it was inside the word "NOT held
# certifications" was invisible to a proximity test.
#
# Proximity is the wrong instrument. What makes a coursework item a false claim
# is a grammatical frame that attaches "certified" TO IT — "certified in X",
# "X certification", "holds X" — so that is what is matched, per item.
_D1_DISCLAIMER = re.compile(
    r"\bcoursework\b|\bcourse work\b|\bstudied?\b|\bstudy\b|\bmodules?\b"
    r"|\bnot (?:a |an )?(?:held )?certifi\w*\b|\bnever (?:a )?certifi\w*\b"
    r"|\bnot certified\b|\bdistance learning\b|\bremote study\b"
    r"|\bcurriculum\b|\bsyllabus\b|\bnot (?:a |an )?credential\b", re.I)


def _loose(term: str) -> str:
    """
    A pattern that matches the term however its dashes and spaces are typeset.

    The profile writes "AWS Certified Developer – Associate" with an en dash; a
    CV may well write a hyphen, an em dash or nothing at all. Matching the exact
    bytes means the rule silently stops applying the moment the model picks a
    different dash — a check that fails open, which is the worst kind.
    """
    parts = [re.escape(p) for p in re.split(r"[\s\-–—]+", term) if p]
    return r"[\s\-–—]+".join(parts) if parts else re.escape(term)


def _d1_frame(term: str) -> re.Pattern[str]:
    """Certification language pointed AT this item, rather than merely near it."""
    t = _loose(term)
    return re.compile(
        rf"(?:certified|accredited|qualified|licen[cs]ed)\s+(?:in\s+|as\s+|with\s+)?{t}"
        rf"|{t}\s*[-–—:]?\s*(?:certified|certification|certificate|credential|accreditation)\b"
        rf"|\b(?:holds?|holding|earned|achieved|awarded)\s+"
        rf"(?:a\s+|an\s+|the\s+|my\s+|his\s+)?{t}",
        re.I)


# The shapes vendor exam codes actually take in this profile: AZ-900, 70-480,
# 98-361, 1Z0-808, DVA-C01, BH0-010. A code is what a CV would cite, so it has
# to be a search key in its own right and not only part of a long product name.
_EXAM_CODE = re.compile(r"\b(?:[A-Z]{2,4}\d?|\d[A-Z]\d|\d{2,3})-[A-Z]?\d{2,3}\b")


def _coursework_keys(profile: Profile) -> list[str]:
    """
    What to look for, per coursework item.

    The full name where it is distinctive, plus the exam code where there is one
    — "AZ-900", "70-480", "1Z0-808" are the strings a CV would actually use, and
    the old `core[:28]` truncation cut "AWS Certified Developer – Associate"
    into "AWS Certified Developer – As", which matches nothing.
    """
    items = profile.raw["certifications"]["coursework_completed"]["items"]
    by_id = {i.get("id"): i for i in items}
    keys: list[str] = []
    for cid in profile.coursework_ids:
        name = str((by_id.get(cid) or {}).get("name", ""))
        core = re.split(r"[(\[]", name)[0].strip(" —–-")
        if not core:
            continue
        keys.append(core)
        keys += _EXAM_CODE.findall(name)
    return keys


def _check_standing_instructions(cv, letter, profile: Profile, r: AuditResult) -> None:
    """docs/06 D1 and the referee removal."""
    blob = _text_of(cv, letter)

    for key in _coursework_keys(profile):
        for m in _d1_frame(key).finditer(blob):
            sentence = _sentence_around(blob, m.start(), m.end())
            if _D1_DISCLAIMER.search(sentence):
                continue                # rendered as study — which is the rule
            r.findings.append(Finding(
                "d1.coursework_as_certification", "block",
                f"{key!r} is IT Academy coursework (D1) and is written here as a "
                f"held credential: {sentence.strip()[:120]!r}", "cv/letter"))
            break

    # The structural version of the same mistake: a skills group headed
    # "Certifications" turns every item under it into a claimed credential, and
    # no amount of sentence-level grammar would show it.
    cert_heading = re.compile(r"certificat|credential|accredit|licen[cs]", re.I)
    coursework_terms = {k.lower() for k in _coursework_keys(profile)}
    for group, items in cv.skills.items():
        if not cert_heading.search(group):
            continue
        for item in items:
            if item.strip().lower() in coursework_terms:
                r.findings.append(Finding(
                    "d1.coursework_as_certification", "block",
                    f"skills group {group!r} lists {item!r}, which is IT Academy "
                    f"coursework (D1) — a certification heading makes it a claim",
                    f"skills[{group}]"))

    if profile.render_referees:
        r.findings.append(Finding(
            "referees.rendered", "block", "referees must never be rendered", "profile"))


def _sentence_around(text: str, start: int, end: int) -> str:
    """The sentence containing a match. Newlines end a sentence — a CV's lines are."""
    left = max(text.rfind(c, 0, start) for c in ".!?\n;")
    right = min((p for p in (text.find(c, end) for c in ".!?\n;") if p != -1),
                default=len(text))
    return text[left + 1: right]


# ---- prohibited content --------------------------------------------------- #

def _check_prohibited_content(cv, letter, r: AuditResult) -> None:
    blob = _text_of(cv, letter)
    for label, pattern in PROHIBITED_PERSONAL.items():
        if re.search(pattern, blob, re.I):
            r.findings.append(Finding(
                "prohibited.personal", "block",
                f"contains prohibited personal information: {label} (docs/08 §1.1)"))
    # Street address / postal code in the contact area.
    if re.search(r"\b\d+\s+[A-Z][a-z]+\s+(Street|St|Road|Rd|Avenue|Ave|Drive|Dr|Flat)\b", blob):
        r.findings.append(Finding(
            "prohibited.street_address", "block",
            "street address present — city + country only (docs/08 §1.3)"))
    if re.search(r"\b[A-Z]\d[A-Z]\s?\d[A-Z]\d\b", blob):
        r.findings.append(Finding(
            "prohibited.postal_code", "block", "postal code present (docs/08 §1.3)"))


def _check_work_permit_placement(cv: GeneratedCV, letter: CoverLetter, r: AuditResult) -> None:
    """
    docs/08 §1.2 — the correction that matters most.

    Work-permit status belongs in cover letter paragraph 4 and NOWHERE else.
    Not the CV, and not scattered through the other letter paragraphs.
    """
    cv_text = _cv_text(cv)
    if m := re.search(WORK_PERMIT_TERMS, cv_text, re.I):
        r.findings.append(Finding(
            "work_permit.on_cv", "block",
            f"CV mentions {m.group(0)!r} — immigration status is not a Canadian "
            "résumé element; it belongs in cover letter paragraph 4 only "
            "(docs/08 §1.2)", "cv"))

    for name, para in (("opening", letter.opening), ("evidence", letter.evidence),
                       ("bridge", letter.bridge)):
        if m := re.search(WORK_PERMIT_TERMS, para, re.I):
            r.findings.append(Finding(
                "work_permit.wrong_paragraph", "warn",
                f"letter.{name} mentions {m.group(0)!r}; keep it to paragraph 4",
                f"letter.{name}"))

    if not re.search(WORK_PERMIT_TERMS, letter.authorisation, re.I):
        r.findings.append(Finding(
            "work_permit.missing", "block",
            "letter paragraph 4 must state the work-permit position plainly",
            "letter.authorisation"))

    # Offering to pay any part of the LMIA cost is illegal (docs/08 §5.1).
    if re.search(r"\b(pay|cover|reimburse|fund)\b[^.]{0,40}\b(LMIA|permit|fee|cost)\b",
                 _text_of(cv, letter), re.I):
        r.findings.append(Finding(
            "lmia.offer_to_pay", "block",
            "appears to offer paying LMIA costs — recovering them from a worker "
            "is illegal (docs/08 §5.1)"))


def _check_banned_phrases(cv, letter, r: AuditResult) -> None:
    blob = _text_of(cv, letter)
    for pat in BANNED_FABRICATION:
        if m := re.search(pat, blob, re.I):
            r.findings.append(Finding(
                "banned.fabrication", "block", f"fabricated-competence phrase: {m.group(0)!r}"))

    for m in re.finditer(r"\bequivalent to\b", blob, re.I):
        window = blob[max(0, m.start() - 120): m.end() + 120]
        if not CREDENTIAL_EQUIVALENCY_CONTEXT.search(window):
            r.findings.append(Finding(
                "banned.fabrication", "block",
                "'equivalent to' used as a competence claim. It is permitted only "
                "in the credential-assessment line (docs/08 §3.1)"))
    for pat in BANNED_GENERIC:
        if m := re.search(pat, blob, re.I):
            r.findings.append(Finding(
                "banned.generic", "block",
                f"AI-genericness tell: {m.group(0)!r} — genericness is what gets "
                "rejected (docs/07 F-D)"))


# ---- format --------------------------------------------------------------- #

def _check_structure(cv: GeneratedCV, r: AuditResult) -> None:
    for group in cv.skills:
        if group.strip().lower() not in PERMITTED_HEADINGS and len(group) > 30:
            r.findings.append(Finding(
                "structure.heading", "warn",
                f"skills group {group!r} is long; parsers prefer short standard labels"))

    if cv.track == "transferable":
        if cv.portfolio_ids:
            r.findings.append(Finding(
                "track_b.portfolio", "warn",
                "portfolio links on a general-work CV — usually noise for these employers"))
        tech = re.compile(r"\b(React|JavaScript|TypeScript|front-?end|WordPress|API|developer)\b", re.I)
        for e in cv.experience:
            joined = " ".join(b.text for b in e.bullets)
            if tech.search(joined) or tech.search(e.display_title):
                r.findings.append(Finding(
                    "track_b.software_above_fold", "block",
                    "software content in the primary Experience section — on Track B "
                    "it belongs under Additional Experience (docs/08 §2.4)", e.role_id))
    else:
        if cv.additional_experience:
            r.findings.append(Finding(
                "track_a.additional", "warn",
                "additional_experience is a Track B construct"))


def _check_dates(cv: GeneratedCV, r: AuditResult) -> None:
    for e in list(cv.experience) + list(cv.additional_experience):
        if DAY_LEVEL_DATE.search(e.dates):
            r.findings.append(Finding(
                "dates.day_level", "block",
                f"day-level date {e.dates!r} — month granularity only (docs/08 §1.4)",
                e.role_id))
        if BARE_MONTH_ABBR_INCONSISTENT.search(e.dates):
            r.findings.append(Finding(
                "dates.inconsistent_abbr", "block",
                "'Sept' is a documented parser failure; use 'Sep'", e.role_id))


def _check_canadian_english(cv, letter, r: AuditResult) -> None:
    blob = _text_of(cv, letter)
    for wrong, right in NON_CANADIAN_SPELLINGS.items():
        if re.search(rf"\b{re.escape(wrong)}\b", blob, re.I):
            r.findings.append(Finding(
                "language.non_canadian_spelling", "block",
                f"{wrong!r} — Canadian English uses {right!r} (docs/08 §1.4)"))
    for word, note in AMBIGUOUS_SPELLINGS.items():
        if re.search(rf"\b{re.escape(word)}\b", blob, re.I):
            r.findings.append(Finding(
                "language.check_spelling", "warn", f"{word!r}: {note}"))


# ---- docs/07 F-D: specificity is the defence ------------------------------ #

# A "concrete particular" is anything that could not appear verbatim on another
# application: a number, a proper noun (employer, town, province, product), or a
# specific physical/technical noun. Deliberately general — the opening paragraph
# is supposed to name THIS employer, who is not in the profile.
_NUMBER = re.compile(r"\b\d[\d,.]*\b")
_PROPER_NOUN = re.compile(r"(?<![.!?]\s)(?<!^)\b([A-Z][a-zA-Z]{2,}(?:\s+[A-Z][a-zA-Z]{2,})*)\b", re.M)
_CONCRETE_NOUN = re.compile(
    r"\b(harness|trench|conduit|pallet|forklift|WHMIS|greenhouse|livestock|dairy|"
    r"poultry|harvest|shift|on-call|scaffold|excavation|hygiene|"
    r"React|TypeScript|JavaScript|WordPress|Active Directory|Exchange|SharePoint)\b", re.I)

# Words that are capitalised but carry no specificity.
_STOPWORD_PROPER = {
    "dear", "hiring", "manager", "sincerely", "yes", "the", "job", "bank",
    "canada", "canadian", "english", "french", "monday", "friday", "north",
    "south", "please", "thank", "regards", "sir", "madam",
}


def _concrete_particulars(text: str) -> set[str]:
    hits: set[str] = set()
    hits |= {m.group(0) for m in _NUMBER.finditer(text)}
    hits |= {m.group(0).lower() for m in _CONCRETE_NOUN.finditer(text)}
    for m in _PROPER_NOUN.finditer(text):
        token = m.group(1)
        if token.lower() not in _STOPWORD_PROPER and len(token) > 2:
            hits.add(token.lower())
    return hits


def _check_specificity(letter: CoverLetter, r: AuditResult) -> None:
    """
    Every paragraph must carry >= 2 concrete particulars. A paragraph that would
    read identically on another application is exactly what gets binned.
    """
    for name, para in (("opening", letter.opening), ("evidence", letter.evidence),
                       ("bridge", letter.bridge)):
        hits = _concrete_particulars(para)
        if len(hits) < 2:
            r.findings.append(Finding(
                "specificity.thin", "block",
                f"letter.{name} has {len(hits)} concrete particular(s); needs >= 2. "
                "A paragraph that would read the same on another application is "
                "the definition of generic (docs/07 F-D)", f"letter.{name}"))


SCREENING_QUESTION = re.compile(r"([^\n?]{10,160}\?)")


def screening_questions(posting_text: str) -> list[str]:
    """
    Questions the posting puts to the applicant.

    The generator feeds this same list into the prompt, so the model is asked to
    answer exactly what the audit will demand answers to. Sharing one function
    is the point — two similar regexes drifting apart would produce a document
    that is blocked for not answering a question it was never shown.

    Deliberately over-inclusive: marketing copy ("Looking for a rewarding
    career?") is caught alongside real screening questions. Answering a
    rhetorical question costs a sentence; missing a real one costs the
    application.
    """
    return [" ".join(q.split()) for q in SCREENING_QUESTION.findall(posting_text or "")]


def _check_screening_questions(letter: CoverLetter, posting_text: str, r: AuditResult) -> None:
    if not posting_text:
        return
    qs = screening_questions(posting_text)
    if qs and not letter.screening_answers:
        r.findings.append(Finding(
            "screening.unanswered", "block",
            f"posting asks {len(qs)} screening question(s) and the letter answers "
            "none — ~30% of LMIA postings ask, and most applicants ignore them",
            "letter.screening_answers"))


_TOKEN = re.compile(r"[A-Za-z0-9]+")
_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
# Words that carry no identifying weight when matching a credential or school.
_WEAK_TOKENS = {"of", "the", "and", "in", "a", "at", "for", "de", "pty", "ltd",
                "division", "school", "college", "institute", "academy", "certificate"}


def _core_tokens(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN.findall(text)
            if t.lower() not in _WEAK_TOKENS and len(t) > 1}


def _same_thing(rendered: str, recorded: str, *, threshold: float = 0.6) -> bool:
    """
    Whether two names refer to the same credential or institution.

    Not equality: a CV legitimately shortens ("National Senior Certificate" for
    "National Senior Certificate (Matric)") and legitimately extends ("Noorder
    Paarl High School, South Africa"). What it may not do is name a different
    school. So the test is overlap of identifying tokens, measured against
    whichever name is shorter — which tolerates both edits and still fails on a
    substitution.
    """
    a, b = _core_tokens(rendered), _core_tokens(recorded)
    if not a or not b:
        return True                     # nothing identifying to compare
    shared = a & b
    return len(shared) / min(len(a), len(b)) >= threshold


def _check_education(cv: GeneratedCV, profile: Profile, r: AuditResult) -> None:
    """
    docs/04 Rule 1, applied to the section it was missing from.

    Education entries carry an `evidence_id`, and until now that was the whole
    check — the id had to exist and be usable, and the credential name,
    institution, year and ECA file number beside it were free text nobody
    verified. The entailment pass does not cover them either: it reads bullets
    and paragraphs, not education records.

    That is the worst place in the document to leave unguarded. A wrong
    graduation year or an invented credential on an application supporting a
    work permit is misrepresentation, and the ICAS file number is a real
    reference an officer can look up.
    """
    for ed in cv.education:
        entry = profile.education_entry(ed.evidence_id)
        if entry is None:
            continue                    # _check_evidence already blocked the id

        if not _same_thing(ed.credential, str(entry.get("credential", ""))):
            r.findings.append(Finding(
                "education.credential_mismatch", "block",
                f"renders credential {ed.credential!r}; the profile records "
                f"{entry.get('credential')!r}", ed.evidence_id))

        if not _same_thing(ed.institution, str(entry.get("institution", ""))):
            r.findings.append(Finding(
                "education.institution_mismatch", "block",
                f"renders institution {ed.institution!r}; the profile records "
                f"{entry.get('institution')!r}", ed.evidence_id))

        known = profile.education_years(ed.evidence_id)
        claimed = set(_YEAR.findall(ed.year or ""))
        if invented := claimed - known:
            r.findings.append(Finding(
                "education.year_mismatch", "block",
                f"claims year(s) {sorted(invented)}; the profile records "
                f"{sorted(known) or 'no year'}", ed.evidence_id))

        _check_eca(ed, entry, r)


def _check_eca(ed, entry: dict, r: AuditResult) -> None:
    """
    docs/08 §3.1 — the equivalency line, with its file number.

    Stating it is a genuine advantage most overseas applicants never take.
    Getting the number wrong turns that advantage into a discrepancy on a
    document an officer can check against ICAS's own records.
    """
    detail = ed.detail or ""
    eca = entry.get("eca")
    if not isinstance(eca, dict):
        if re.search(r"\b(ICAS|WES|IQAS|ICES|educational credential assessment)\b",
                     detail, re.I):
            r.findings.append(Finding(
                "education.eca_invented", "block",
                f"claims a credential assessment for {ed.evidence_id}, which has "
                "none on record", ed.evidence_id))
        return

    recorded = str(eca.get("file_no", "")).strip()
    for found in re.findall(r"\b\d{6,}(?:\s*[A-Z]{2,4})?\b", detail):
        if recorded and found.strip() not in recorded:
            r.findings.append(Finding(
                "education.eca_file_number", "block",
                f"cites assessment file {found.strip()!r}; the profile records "
                f"{recorded!r}", ed.evidence_id))

    equivalency = str(eca.get("canadian_equivalency", "")).strip()
    if equivalency and re.search(r"\bequivalent to\b", detail, re.I):
        if not _same_thing(detail, equivalency, threshold=0.5):
            r.findings.append(Finding(
                "education.eca_equivalency", "warn",
                f"the equivalency line does not state {equivalency!r}",
                ed.evidence_id))


# docs/08 §4, and the standing rule in TRACK_B_GUIDANCE: never claim a ticket he
# does not hold. These are the terms an agricultural, warehouse or trades
# employer reads as a specific qualification — machinery he would be put on, or
# a certificate with an issuing body behind it. Claiming one he lacks is not
# padding, it is a statement an employer can act on and be wrong about.
#
# Deliberately a closed list rather than a general "is this grounded" score.
# Generic descriptors ("physical stamina", "punctuality") score identically to
# invented machinery under any similarity measure, and blocking those would burn
# retries on language that harms nobody.
CREDENTIAL_CLAIMS = re.compile(
    r"\b(fall[- ]arrest|forklift|pallet jack|order picker truck|scissor lift|boom lift|"
    r"skid[- ]steer|backhoe|excavator|bobcat|telehandler|crane|rigging|"
    r"chainsaw|welding|MIG|TIG|arc weld|"
    r"tractor|combine harvester|sprayer|"
    r"WHMIS|TDG|HACCP|first aid|CPR|confined space|fall protection ticket|"
    r"working at heights ticket|scaffold(?:ing)? ticket|H2S|"
    r"pesticide|herbicide|fumigation|"
    r"food handler|food safety certificate|"
    r"class [1-5] licence|class [1-5] license|air brake|"
    r"red seal|journeyman|apprenticeship|trade certificate)\b", re.I)


def _supported_text(profile: Profile) -> str:
    """
    Everything the profile actually says, normalised for phrase matching.

    Hyphens collapse to spaces so "fall-arrest" and "fall arrest" are the same
    claim — the check is about the qualification, not the typography.
    """
    parts: list[str] = []
    for _group, items in (profile.raw.get("skills") or {}).items():
        if isinstance(items, dict):
            if items.get("verify"):
                continue
            items = items.get("items", [])
        parts += [str(i) for i in items or []]
    parts += [ev.text for ev in profile.evidence.values() if ev.usable]
    parts += [r.title_as_held for r in profile.roles if not r.excluded]
    parts += [r.canadian_title for r in profile.roles if not r.excluded]
    return re.sub(r"[\s\-–—]+", " ", " ".join(parts)).lower()


def _grounding_corpus(profile: Profile) -> set[str]:
    """Every word the profile supports, for the warn-level check."""
    return _core_tokens(_supported_text(profile))


# docs/08 §4 and TRACK_B_GUIDANCE: *stating willingness to obtain* a ticket is
# honest and expected — it is the recommended bridge sentence, and so is saying
# plainly that he does not have one. Only claiming to hold a ticket is the
# problem, so the rule has to tell three things apart, not two.
#
# The first live batch got this wrong three different ways and blocked three
# correct documents:
#
#   "I will take that training exactly as given, including any WHMIS or
#    workplace safety course Mucci Farms requires"        — "will", not "would"
#   "I have not operated or maintained farm machinery such as a tractor"
#                                                          — an outright denial
#   "I hold no farm safety, WHMIS or first aid certificate"
#                                          — a hold verb whose negation follows
#
# Each of those is the sentence docs/08 §4 asks for. All three now pass.

WILLINGNESS = re.compile(
    r"\b(willing|prepared|happy|ready|available|keen) to\b"
    r"|\b(?:will|would|can|could|intend to|plan to|expect to|am able to)\s+"
    r"(?:also\s+|gladly\s+|happily\s+)?"
    r"(?:complete|obtain|take|get|do|attend|sit|earn|arrange|undertake|"
    r"enrol|enroll|study|learn|train|qualify|acquire)\b"
    r"|\bbefore (?:starting|I start|my start|the first shift|my first shift)\b"
    r"|\bif required\b|\bas required\b|\bif you require\b"
    r"|\bany(?:thing)? [^.]{0,60}?\b(?:requires?|require|you provide|provided)\b"
    r"|\bwhatever [^.]{0,60}?\b(?:requires?|require|training|course)\b"
    r"|\bemployer[- ](?:paid|provided|supplied)\b"
    r"|\bon[- ]the[- ]job training\b", re.I)

# A plain statement that he does NOT have the thing, or has never done it. These
# read as claims to a keyword matcher and as honesty to a human, and the human
# is right.
NOT_HELD = re.compile(
    r"\b(?:do(?:es)?|did)\s+not\s+(?:yet\s+)?(?:hold|have|possess)\b"
    r"|\bhold(?:s)?\s+(?:no|none|neither)\b"
    r"|\bhave\s+(?:no|none|neither)\b"
    r"|\bnone\s+of\s+(?:which|these|those|them|it)\b"
    r"|\bnot\s+(?:currently\s+|yet\s+)?(?:certified|licen[cs]ed|ticketed|qualified|accredited)\b"
    r"|\bno\s+(?:\w+[-\s]){0,4}?(?:certificate|certification|ticket|licence|license|credential)s?\b"
    r"|\bwithout\s+(?:a|an|any)\s+(?:\w+[-\s]){0,4}?"
    r"(?:certificate|certification|ticket|licence|license|credential|experience)\b",
    re.I)

DENIAL = re.compile(
    r"\b(?:have|has|had|I|he)\s+(?:never|not)\s+(?:\w+\s+){0,3}?"
    r"(?:worked|used|operated|driven|run|held|done|completed|obtained|been|"
    r"cut|mixed|hoed|harvested|picked|packed|supervised|maintained|handled|"
    r"pruned|milked|slaughtered|butchered|welded|framed|installed)\b"
    r"|\bnever\s+(?:\w+\s+){0,2}?(?:operated|used|held|worked|driven|done|"
    r"handled|supervised)\b"
    r"|\bno experience (?:with|in|of|on|as)\b"
    r"|\b(?:will|would|do) not pretend\b"
    r"|\bwhat I have not done\b|\bwhat I have never done\b", re.I)

# An affirmative claim to hold the thing. Checked in a tighter window, because
# willingness language elsewhere in the paragraph must not launder it: "I have
# not worked on a farm, but I hold a forklift ticket" contains a denial and a
# held claim, and only the second one matters.
HELD_CLAIM = re.compile(
    r"\b(holds?|holding|possess(?:es)?)\b"
    r"|\b(?:am|is|are|was|were) (?:certified|licen[cs]ed|ticketed|qualified|accredited)\b"
    r"|\bcertified in\b"
    r"|\bhave (?:a|an|my|valid|current)\b", re.I)

HELD_WINDOW = 80
WILLINGNESS_WINDOW = 200


def _check_skill_claims(cv: GeneratedCV, letter: CoverLetter, profile: Profile,
                        r: AuditResult) -> None:
    recorded = _supported_text(profile)
    supported = _core_tokens(recorded)

    # The letter is scanned too: "I hold a forklift ticket" in paragraph 2 is
    # the same misrepresentation as a skills bullet, and the bridge paragraph
    # is exactly where the temptation lives.
    for where, text in (("cv", _cv_text(cv)), ("letter", _letter_text(letter))):
        for match in CREDENTIAL_CLAIMS.finditer(text):
            term = match.group(0)
            # The whole phrase must be on record, not merely its words. "food"
            # and "first" both appear in this profile in innocent contexts, and
            # a token-level test would let "food handler certificate" and
            # "first aid" through on the strength of them.
            if re.sub(r"[\s\-–—]+", " ", term).lower() in recorded:
                continue
            near = text[max(0, match.start() - HELD_WINDOW):
                        match.end() + HELD_WINDOW]
            wide = text[max(0, match.start() - WILLINGNESS_WINDOW):
                        match.end() + WILLINGNESS_WINDOW]

            # Asserted = a hold verb close by that is not itself negated. The
            # negation test runs on the same narrow window, so "I hold no WHMIS
            # certificate" cancels its own hold verb while "I have not worked on
            # a farm, but I hold a forklift ticket" does not.
            asserted = HELD_CLAIM.search(near) and not NOT_HELD.search(near)
            honest = (NOT_HELD.search(wide) or DENIAL.search(wide)
                      or WILLINGNESS.search(wide))
            if not asserted and honest:
                continue                # disclaimed, denied, or offered — fine
            r.findings.append(Finding(
                "skills.unheld_credential", "block",
                f"claims {term!r}, which appears nowhere in the profile, and not "
                "as something he would obtain or has said he lacks. An employer "
                "reads this as a ticket he already holds (docs/08 §4)", where))

    # Everything else gets a warning, not a block: a line that reads oddly is
    # worth a human glance, but forcing a retry over "physical stamina" spends
    # a generation on nothing.
    for group, items in cv.skills.items():
        for item in items:
            tokens = _core_tokens(item)
            if tokens and len(tokens & supported) / len(tokens) < 0.5:
                r.findings.append(Finding(
                    "skills.thinly_grounded", "warn",
                    f"{item!r} has little support in the profile", f"skills[{group}]"))


def _check_languages(cv: GeneratedCV, profile: Profile, r: AuditResult) -> None:
    """
    Five languages are on record. A sixth is an invention, and a language claim
    is one an employer or an officer can test in about a minute.
    """
    known = {str(l["language"]).lower(): l
             for l in profile.raw.get("languages", []) or []}

    for entry in cv.languages:
        name = re.split(r"[(\[\-–—:,]", entry)[0].strip()
        if not name:
            continue
        record = known.get(name.lower())
        if record is None:
            r.findings.append(Finding(
                "languages.unknown", "block",
                f"claims {name!r}; the profile records {sorted(known)}",
                "cv.languages"))
            continue
        claims_native = re.search(r"\b(native|mother tongue|first language)\b",
                                  entry, re.I)
        if claims_native and str(record.get("speak", "")).lower() != "native":
            r.findings.append(Finding(
                "languages.overstated", "block",
                f"claims {name!r} as a native language; the profile records "
                f"speak={record.get('speak')!r}", "cv.languages"))


# docs/08 §1.4 — metric where measurements appear, "but mirror the employer":
# lifting capacities get quoted in lb as often as kg, and matching the posting's
# own unit reads better than correcting it. So an imperial unit is only odd when
# the posting never used one.
IMPERIAL = re.compile(
    r"\b\d+\s?(lbs?|pounds?|ft|feet|foot|inch(?:es)?|miles?|°?F|fahrenheit)\b", re.I)


def _check_units(cv: GeneratedCV, letter: CoverLetter, posting_text: str,
                 r: AuditResult) -> None:
    if not posting_text:
        return
    posting_uses_imperial = bool(IMPERIAL.search(posting_text))
    if posting_uses_imperial:
        return
    for match in IMPERIAL.finditer(_text_of(cv, letter)):
        r.findings.append(Finding(
            "units.imperial", "warn",
            f"{match.group(0)!r} — Canada is metric and this posting used metric "
            "units (docs/08 §1.4)", "cv/letter"))


def _check_employer_context(cv: GeneratedCV, r: AuditResult) -> None:
    """docs/08 §3.2 — a Canadian reader does not know these employers."""
    for e in list(cv.experience) + list(cv.additional_experience):
        if not e.employer_context:
            r.findings.append(Finding(
                "context.missing", "warn",
                f"{e.employer!r} has no context clause; a Canadian reader will not "
                "recognise it (docs/08 §3.2)", e.role_id))


# ---- helpers -------------------------------------------------------------- #

def _cv_text(cv: GeneratedCV) -> str:
    parts: list[str] = [cv.headline, cv.summary, cv.availability or ""]
    for e in list(cv.experience) + list(cv.additional_experience):
        parts += [e.display_title, e.employer, e.employer_context or "",
                  e.location, e.dates, e.employment_type or ""]
        parts += [b.text for b in e.bullets]
    for ed in cv.education:
        parts += [ed.credential, ed.institution, ed.year, ed.detail or ""]
    for group, items in cv.skills.items():
        parts += [group, *items]
    parts += cv.languages
    return "\n".join(p for p in parts if p)


def _letter_text(letter: CoverLetter) -> str:
    return "\n".join([
        letter.greeting, letter.opening, letter.evidence, letter.bridge,
        letter.authorisation, *letter.screening_answers, letter.signoff,
    ])


def _text_of(cv: GeneratedCV, letter: CoverLetter) -> str:
    return _cv_text(cv) + "\n" + _letter_text(letter)


__all__ = ["audit", "AuditResult", "Finding", "screening_questions"]
