"""
Shared test fixtures.

The Ridge Farms application is the running example across every layer's tests —
a Track B application to a real LMIA farm posting, which is the case the whole
system exists for. Keeping one definition means a change to the profile or the
schema breaks one place, not three, and the audit, round-trip and generator
tests are demonstrably talking about the same document.

Every builder takes keyword overrides so a test can bend exactly one field and
leave the rest known-good.
"""

from __future__ import annotations

from northbound.generate.schemas import (
    Application, Bullet, CoverLetter, DocumentSet, EducationEntry,
    ExperienceEntry, GeneratedCV,
)
from northbound.profile import load_profile

PROFILE = load_profile()

POSTING_BODY = """\
Ridge Farms is hiring general farm workers for the greenhouse operation in
Leamington, Ontario. Duties include planting, pruning, harvesting and packing
produce, and general clean-up of the growing areas.

Requirements: no formal education required; on-the-job training provided.
Physically demanding work in a hot greenhouse environment, standing for extended
periods, repetitive tasks, lifting up to 20 kg.

Are you available to work weekends and overtime during the harvest season?
"""


def letter(**over) -> CoverLetter:
    base = dict(
        greeting="Dear Hiring Manager,",
        opening=("I am applying for the general farm worker role at Ridge Farms in "
                 "Leamington, Ontario, advertised on Job Bank."),
        evidence=("I worked about 18 months as a general electrical assistant with "
                  "Cumpsty Electrical on estate construction sites in Paarl, and "
                  "spent a year in kitchen and food production at McDonald's."),
        evidence_ids=["gen.cumpsty.h1", "gen.mcdonalds.h1"],
        bridge=("I have not worked on a farm, but the work at Cumpsty was outdoors "
                "and physical, and I held a harness on multi-storey roofs in Paarl."),
        bridge_evidence_ids=["gen.painter.h2"],
        authorisation=("I am in Cape Town, South Africa and would need a work permit "
                       "supported by an LMIA. I hold an ICAS assessment for Canada."),
        screening_answers=["Yes, I am available for weekend and overtime work "
                           "through the harvest season."],
    )
    base.update(over)
    return CoverLetter(**base)


def cv(**over) -> GeneratedCV:
    """Minimal clean Track B CV — one role, enough to exercise every rule."""
    base = dict(
        track="transferable",
        target_noc="85101",
        headline="General Farm Worker",
        summary=("Physical worker with 18 months on construction sites in Paarl and "
                 "a year in food production at McDonald's."),
        summary_evidence_ids=["gen.cumpsty.h1"],
        skills={"Practical": ["working at height with fall-arrest harness", "hand tools"]},
        experience=[ExperienceEntry(
            role_id="gen.cumpsty",
            display_title="Electrician's Helper / Construction Labourer (NOC 75110)",
            employer="Cumpsty Electrical",
            employer_context="residential estate electrical contractor, Paarl",
            location="Paarl, Western Cape, South Africa",
            dates=PROFILE.role("gen.cumpsty").display_dates,
            employment_type=None,
            bullets=[Bullet(
                text="Assisted qualified electricians on residential estate construction sites.",
                evidence_ids=["gen.cumpsty.h1"])],
        )],
        education=[EducationEntry(
            evidence_id="edu.matric", credential="National Senior Certificate",
            institution="Noorder Paarl High School", year="2016",
            detail="Assessed by ICAS as equivalent to Canadian Secondary School Graduation.")],
        languages=["English", "French"],
    )
    base.update(over)
    return GeneratedCV(**base)


def full_cv(**over) -> GeneratedCV:
    """
    The complete Track B document — several relevant roles plus the software
    career compressed underneath. This is the shape the renderer and the ATS
    round-trip are tested against, because section ordering only means something
    when there is more than one section to order.
    """
    base = dict(
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
                           evidence_ids=["gen.cumpsty.h1"]),
                    Bullet(text="Carried out wall chasing, trenching and excavation for "
                                "cable and conduit runs.",
                           evidence_ids=["gen.cumpsty.h2"]),
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
                    evidence_ids=["gen.mcdonalds.h1"])],
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
                evidence_ids=["exp.kurtosys.h1"])],
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
    base.update(over)
    return GeneratedCV(**base)


def track_a_cv(**over) -> GeneratedCV:
    """
    The developer CV — the other half of the system, and the half that had no
    fixture until a Track-A-only bug went unnoticed ("single-page applications"
    blocking as marital status). Ordinary front-end vocabulary belongs here for
    exactly that reason.
    """
    base = dict(
        track="direct",
        target_noc="21234",
        headline="Front End Developer",
        summary=("Front-end developer working remotely for a Netherlands company, "
                 "with delivery for clients in the US, Canada, the UK and the "
                 "Netherlands, including BMO."),
        summary_evidence_ids=["exp.databalk.h1", "exp.kurtosys.h3"],
        skills={
            "Frontend": ["JavaScript (ES6+)", "TypeScript", "React.js",
                         "single-page applications", "responsive design"],
            "CMS": ["WordPress", "custom theme and plugin front-end work"],
            "Tooling": ["Git", "VS Code", "Jira"],
        },
        experience=[
            ExperienceEntry(
                role_id="exp.databalk",
                display_title="Front-End Developer (NOC 21234)",
                employer="DataBalk",
                employer_context="Netherlands software company, remote",
                location="Netherlands (Remote)",
                dates=PROFILE.role("exp.databalk").display_dates,
                employment_type="Full-time",
                bullets=[Bullet(
                    text="Develops and maintains responsive front-end interfaces "
                         "for DataBalk platforms.",
                    evidence_ids=["exp.databalk.h1"])],
            ),
            ExperienceEntry(
                role_id="exp.kurtosys",
                display_title="Front-End Developer (NOC 21234)",
                employer="Kurtosys Systems",
                employer_context="FinTech / asset-management technology",
                location="Cape Town, South Africa",
                dates=PROFILE.role("exp.kurtosys").display_dates,
                employment_type="Full-time",
                bullets=[
                    Bullet(text="Built and maintained responsive financial websites "
                                "for international clients.",
                           evidence_ids=["exp.kurtosys.h1"]),
                    Bullet(text="Worked directly with clients across the US, Canada, "
                                "the UK and the Netherlands.",
                           evidence_ids=["exp.kurtosys.h3"]),
                ],
            ),
        ],
        education=[EducationEntry(
            evidence_id="edu.matric", credential="National Senior Certificate",
            institution="Noorder Paarl High School", year="2016",
            detail="Assessed by ICAS as equivalent to Canadian Secondary School "
                   "Graduation. File 24080341 IMM.")],
        languages=["English", "French"],
        portfolio_ids=["pf.bmo", "pf.cti"],
    )
    base.update(over)
    return GeneratedCV(**base)


def track_a_letter(**over) -> CoverLetter:
    base = dict(
        greeting="Dear Hiring Manager,",
        opening=("I am applying for the front end developer role at Northwind "
                 "Digital in Toronto, advertised on Job Bank."),
        evidence=("I work remotely for DataBalk in the Netherlands, and at "
                  "Kurtosys Systems I built financial websites for clients "
                  "across the US, Canada and the UK, including BMO."),
        evidence_ids=["exp.databalk.h1", "exp.kurtosys.h3"],
        bridge=("Working across those time zones from Cape Town is the same "
                "arrangement Northwind would be hiring into, and the BMO work "
                "was for a Canadian bank."),
        bridge_evidence_ids=["exp.kurtosys.h3"],
        authorisation=("I am in Cape Town, South Africa and would need a work "
                       "permit supported by an LMIA. I hold an ICAS assessment "
                       "for Canada."),
    )
    base.update(over)
    return CoverLetter(**base)


def app(cv_=None, letter_=None) -> Application:
    return Application(
        posting_id="49816590", posting_title="general labourer - farm",
        employer="Ridge Farms", track="transferable",
        cv=cv_ or cv(), letter=letter_ or letter(),
    )


def docset(cv_=None, letter_=None) -> DocumentSet:
    return DocumentSet(cv=cv_ or cv(), letter=letter_ or letter())


def track_a_app(cv_=None, letter_=None) -> Application:
    return Application(
        posting_id="49900001", posting_title="front end developer",
        employer="Northwind Digital", track="direct",
        cv=cv_ or track_a_cv(), letter=letter_ or track_a_letter(),
    )


__all__ = ["PROFILE", "POSTING_BODY", "letter", "cv", "full_cv", "app", "docset",
           "track_a_cv", "track_a_letter", "track_a_app"]
