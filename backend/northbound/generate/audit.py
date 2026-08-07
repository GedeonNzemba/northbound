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
PROHIBITED_PERSONAL = {
    "date of birth": r"\b(date of birth|d\.?o\.?b\.?)\b",
    "age": r"\b(?:I am |aged )\d{2} years old\b",
    "marital status": r"\b(marital status|married|single|divorced)\b",
    "nationality": r"\b(nationality|citizenship)\s*[:=]",
    "gender": r"\b(gender|sex)\s*[:=]",
    "SIN": r"\b(social insurance number|\bSIN\b)",
    "photo": r"\b(photograph attached|photo attached)\b",
    "religion": r"\breligion\s*[:=]",
    "references-on-cv": r"\breferences (are )?available (up)?on request\b",
    "salary expectation": r"\b(salary expectation|expected salary|current salary)\b",
}

# docs/08 §1.2 — belongs in the cover letter ONLY.
WORK_PERMIT_TERMS = r"\b(work permit|LMIA|visa sponsorship|sponsorship|work authorisation|work authorization|open permit|closed permit)\b"

# docs/08 §1.4 — Canadian English.
US_SPELLINGS = {
    "color": "colour", "behavior": "behaviour", "favorite": "favourite",
    "center": "centre", "meter": "metre", "organization": "organisation",
    "organize": "organise", "recognize": "recognise", "analyze": "analyse",
    "traveled": "travelled", "canceled": "cancelled", "enrolled ": "enrolled ",
    "labor": "labour", "neighbor": "neighbour", "defense": "defence",
    "fulfill": "fulfil", "catalog": "catalogue", "program ": "programme ",
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

    _check_evidence(cv, letter, profile, r)
    _check_education(cv, profile, r)
    _check_standing_instructions(cv, letter, profile, r)
    _check_prohibited_content(cv, letter, r)
    _check_work_permit_placement(cv, letter, r)
    _check_banned_phrases(cv, letter, r)
    _check_structure(cv, r)
    _check_dates(cv, r)
    _check_canadian_english(cv, letter, r)
    _check_specificity(letter, r)
    _check_screening_questions(letter, posting_text, r)
    _check_employer_context(cv, r)
    return r


# ---- truth ---------------------------------------------------------------- #

def _all_cited_ids(cv: GeneratedCV, letter: CoverLetter) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    out += [(i, "cv.summary") for i in cv.summary_evidence_ids]
    for e in list(cv.experience) + list(cv.additional_experience):
        out += [(b.evidence_id, f"cv.experience[{e.role_id}]") for b in e.bullets]
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


def _check_standing_instructions(cv, letter, profile: Profile, r: AuditResult) -> None:
    """docs/06 D1 and the referee removal."""
    blob = _text_of(cv, letter)

    # D1 — IT Academy items are coursework, never held credentials.
    cert_words = r"(certified|certification|credential|accredited|holds? the)"
    for cid in profile.coursework_ids:
        item = next(
            (i for i in profile.raw["certifications"]["coursework_completed"]["items"]
             if i.get("id") == cid), None)
        if not item:
            continue
        name = item.get("name", "")
        core = re.split(r"[—(]", name)[0].strip()
        if not core:
            continue
        for m in re.finditer(re.escape(core[:28]), blob, re.I):
            window = blob[max(0, m.start() - 90): m.end() + 90]
            if re.search(cert_words, window, re.I):
                r.findings.append(Finding(
                    "d1.coursework_as_certification", "block",
                    f"'{core}' is IT Academy coursework (D1) but appears near "
                    f"certification language", "cv/letter"))
                break

    if profile.render_referees:
        r.findings.append(Finding(
            "referees.rendered", "block", "referees must never be rendered", "profile"))


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
    for us, ca in US_SPELLINGS.items():
        if re.search(rf"\b{re.escape(us.strip())}\b", blob, re.I):
            r.findings.append(Finding(
                "language.us_spelling", "block",
                f"US spelling {us.strip()!r} — Canadian English requires {ca.strip()!r}"))


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
