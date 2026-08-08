"""
Typed output contract for generated documents.

The generator returns these objects — never markdown, never prose to be parsed.
Every claim-bearing string carries the profile ids it came from, which is what
makes the audit in `audit.py` possible at all (docs/04 Rule 2). Those ids are a
LIST everywhere, including on a single bullet: real sentences draw on more than
one record, and a citation field that cannot say so turns honest writing into an
entailment failure.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Track = Literal["direct", "transferable"]


class Bullet(BaseModel):
    """
    One line of a work-experience entry.

    `evidence_ids` is a list because a good bullet often merges two profile
    entries — "Provided on-site support for a 150-user network and set up
    workstations, switches and printers" is one natural line drawn from two
    records. With a single id the model had to pick one and the entailment pass
    correctly rejected the other half, so the schema forced a choice between
    writing badly and citing incompletely. It cites what it drew on.
    """

    text: str = Field(description="The bullet as it will appear. Starts with a verb, past tense for past roles.")
    evidence_ids: list[str] = Field(
        min_length=1,
        description="ids of the master-profile entries this is drawn from. All must exist. "
                    "Cite every entry the sentence uses — one if it draws on one, several if it merges several.",
    )


class ExperienceEntry(BaseModel):
    role_id: str = Field(description="id of the role in master-profile.yaml")
    display_title: str = Field(description="Title as rendered, e.g. 'Front-End Developer (NOC 21234)'")
    employer: str
    employer_context: str | None = Field(
        default=None,
        description="One clause telling a Canadian reader what this employer is. docs/08 §3.2.",
    )
    location: str
    dates: str = Field(description="Mon YYYY – Mon YYYY. Never day-level.")
    employment_type: str | None = Field(
        default=None,
        description="Full-time / Contract / Part-time / Freelance. None where genuinely unknown — never guessed.",
    )
    bullets: list[Bullet]


class EducationEntry(BaseModel):
    evidence_id: str
    credential: str
    institution: str
    year: str
    detail: str | None = Field(
        default=None,
        description="e.g. the ICAS equivalency line with its file number. docs/08 §3.1.",
    )


class GeneratedCV(BaseModel):
    track: Track
    target_noc: str = Field(description="NOC 2021 code this CV is aimed at")
    headline: str = Field(description="The target role in the employer's own words")
    summary: str = Field(description="2-4 lines. Plain language on Track B.")
    summary_evidence_ids: list[str]
    skills: dict[str, list[str]] = Field(description="Grouped. Practical first on Track B.")
    experience: list[ExperienceEntry]
    additional_experience: list[ExperienceEntry] = Field(
        default_factory=list,
        description="Track B only — the software career, compressed. docs/08 §2.4.",
    )
    education: list[EducationEntry]
    languages: list[str]
    portfolio_ids: list[str] = Field(default_factory=list, description="Track A only, 3-4 max")
    availability: str | None = None


class CoverLetter(BaseModel):
    """
    Four paragraphs, docs/08 §5. Kept as separate fields rather than one blob so
    the audit can check each one's job independently — notably that paragraph 4
    is where work-permit status lives and that it appears nowhere else.
    """

    greeting: str = Field(description="Named person where the posting gives one, else 'Dear Hiring Manager,'")
    opening: str = Field(description="P1 — the role, where seen, one specific detail about THIS employer")
    evidence: str = Field(description="P2 — two or three cited specifics")
    evidence_ids: list[str]
    bridge: str = Field(description="P3 — honest bridge (Track B) or depth argument (Track A)")
    bridge_evidence_ids: list[str] = Field(default_factory=list)
    authorisation: str = Field(description="P4 — work-permit position, stated plainly. ONLY here.")
    screening_answers: list[str] = Field(
        default_factory=list,
        description="Direct answers to the posting's screening questions. ~30% of LMIA postings ask.",
    )
    signoff: str = "Sincerely,"


class DocumentSet(BaseModel):
    """
    What the model returns in one call.

    CV and letter are generated together rather than in two calls, because the
    letter must not repeat what the CV already says and must point at it — a
    consistency the model can only maintain if it writes both at once. The
    posting identifiers are attached in code afterwards; asking the model to
    echo them back would spend tokens on facts we already hold and give it one
    more thing to get wrong.
    """

    cv: GeneratedCV
    letter: CoverLetter


class Application(BaseModel):
    posting_id: str
    posting_title: str
    employer: str
    track: Track
    cv: GeneratedCV
    letter: CoverLetter


__all__ = [
    "Bullet", "ExperienceEntry", "EducationEntry",
    "GeneratedCV", "CoverLetter", "DocumentSet", "Application", "Track",
]
