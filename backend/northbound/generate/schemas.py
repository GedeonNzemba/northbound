"""
Typed output contract for generated documents.

The generator returns these objects — never markdown, never prose to be parsed.
Every claim-bearing string carries the `evidence_id` it came from, which is what
makes the audit in `audit.py` possible at all (docs/04 Rule 2).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Track = Literal["direct", "transferable"]


class Bullet(BaseModel):
    """One line of a work-experience entry."""

    text: str = Field(description="The bullet as it will appear. Starts with a verb, past tense for past roles.")
    evidence_id: str = Field(description="id of the master-profile entry this is drawn from. Must exist.")


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


class Application(BaseModel):
    posting_id: str
    posting_title: str
    employer: str
    track: Track
    cv: GeneratedCV
    letter: CoverLetter


__all__ = [
    "Bullet", "ExperienceEntry", "EducationEntry",
    "GeneratedCV", "CoverLetter", "Application", "Track",
]
