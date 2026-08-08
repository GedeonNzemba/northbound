"""
The generator — docs/04.

One posting in, one `Application` out, or nothing sent. The pipeline is:

    draft ──► Layer 1 audit ──► Layer 3 entailment ──► ready
                  │                    │
                  └──── repair ────────┘   (once, then parked)

Three decisions here are the whole design:

**The gate is closed by default.** `status` is "parked" unless every check
passed. A parked application is a real output — documents exist and a human can
look at them — it simply is never auto-sent. Nothing in this module can produce
a sendable document by failing to run a check, only by passing one.

**Audit before entailment.** The audit is free and instant; entailment is one
model call per bullet. Running the cheap deterministic layer first means an
obviously-broken draft costs nothing to reject. The consequence is that a draft
which fails the audit spends its retry there and gets parked if entailment then
fails — which is the conservative outcome and the one docs/04 specifies.

**Repair, not regeneration.** The retry carries the previous draft and the exact
failures back to the model. Asking again with the same prompt would resample the
same distribution and usually reproduce the same fault.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml

from ..profile import Profile
from .audit import AuditResult, audit, screening_questions
from .entailment import Cache as EntailmentCache, EntailmentResult
from .entailment import failures as entailment_failures, verify_application
from .llm import (
    DEFAULT_MODEL, DEFAULT_VERIFY_MODEL, GENERATION_MAX_TOKENS, Client,
    UsageTally, structured_call,
)
from .prompts import TASK_DIRECTIVE, posting_block, retry_block, system_blocks
from .schemas import Application, DocumentSet, Track

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SOURCES = REPO_ROOT / "config" / "sources.yaml"

Status = Literal["ready", "parked"]


class GenerationError(RuntimeError):
    """The pipeline could not run — distinct from a document that failed a check."""


class LayoutError(GenerationError):
    """The rendered document breaks a layout rule that only rendering reveals."""


# docs/08 §1.5. Track B is "1 page, firmly" — a farm employer scanning fifty
# applications does not read page two — and Track A is 2, because one under-sells
# seven years of work. Three is a European convention and reads as not knowing
# the market.
MAX_PAGES = {"transferable": 1, "direct": 2}


# --------------------------------------------------------------------------- #
# Input
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Posting:
    """
    A Job Bank posting as the generator needs it.

    Deliberately dumb: whatever the scraper produces gets normalised into this
    before it reaches the model, so the generator has no opinion about HTML,
    pagination or the two-click email reveal.
    """

    posting_id: str
    title: str
    employer: str
    body: str
    url: str = ""
    location: str = ""
    noc: str = ""
    queue: str = ""                       # lmia_approved | international_candidates
    screening: tuple[str, ...] = ()       # explicit questions, if the scraper found them

    @property
    def questions(self) -> list[str]:
        """Explicit questions where the scraper found them, else parsed from the body."""
        return list(self.screening) or screening_questions(self.body)

    @property
    def slug(self) -> str:
        s = re.sub(r"[^A-Za-z0-9]+", "-", f"{self.employer}-{self.title}").strip("-")
        return re.sub(r"-{2,}", "-", s)[:70]


# --------------------------------------------------------------------------- #
# Track selection
# --------------------------------------------------------------------------- #

@lru_cache(maxsize=4)
def _tech_filters(sources_path: str) -> tuple[frozenset[str], tuple[str, ...]]:
    """
    The NOC codes and title keywords that mark a role as inside his profession.

    Read from config/sources.yaml rather than restated here, so the occupation
    definition lives in exactly one place and a change to the queue policy cannot
    silently disagree with the track chooser.
    """
    raw = yaml.safe_load(Path(sources_path).read_text(encoding="utf-8")) or {}
    for s in raw.get("searches", []) or []:
        pol = s.get("apply_policy") or {}
        if pol.get("role_filter") == "TECH_ONLY":
            return (frozenset(str(n) for n in pol.get("include_noc", []) or []),
                    tuple(str(k).lower() for k in pol.get("include_title_keywords", []) or []))
    raise GenerationError(f"no TECH_ONLY queue found in {sources_path}")


def choose_track(posting: Posting, *, sources_path: Path | str | None = None) -> Track:
    """
    Track A (direct) if the posting is his actual profession, else Track B.

    This is per-posting occupation fit, NOT per-queue. The queues carry a default
    `cv_track`, but the LMIA sweep measured two tech roles among its 112 postings
    — and those two deserve the developer CV, not a transferable one. Occupation
    decides the document; the queue decides only whether we apply at all (D6).
    """
    nocs, keywords = _tech_filters(str(sources_path or DEFAULT_SOURCES))
    if posting.noc and posting.noc.strip() in nocs:
        return "direct"
    title = posting.title.lower()
    return "direct" if any(k in title for k in keywords) else "transferable"


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #

@dataclass
class GenerationOutcome:
    posting: Posting
    track: Track
    status: Status
    application: Application | None = None
    audit: AuditResult | None = None
    entailment: list[EntailmentResult] = field(default_factory=list)
    attempts: int = 0
    parked_reason: str = ""
    usage: UsageTally = field(default_factory=UsageTally)

    @property
    def ready(self) -> bool:
        return self.status == "ready" and self.application is not None

    def report(self) -> str:
        head = (f"{self.status.upper()}  {self.posting.employer} — "
                f"{self.posting.title}  [track {self.track}, "
                f"{self.attempts} attempt(s)]")
        lines = [head]
        if self.parked_reason:
            lines.append(f"  reason: {self.parked_reason}")
        if self.audit is not None:
            lines += ["  " + line for line in self.audit.report().splitlines()]
        bad = entailment_failures(self.entailment)
        if bad:
            lines.append(f"  entailment: {len(bad)} unsupported claim(s)")
            lines += ["  " + line for r in bad for line in str(r).splitlines()]
        elif self.entailment:
            lines.append(f"  entailment: {len(self.entailment)}/{len(self.entailment)} supported")
        lines += ["  " + line for line in self.usage.report().splitlines()]
        return "\n".join(lines)


# --------------------------------------------------------------------------- #
# The pipeline
# --------------------------------------------------------------------------- #

def _draft(client: Client, posting: Posting, profile: Profile, track: Track, *,
           model: str, max_tokens: int, repair: str | None,
           tally: UsageTally, effort: str | None = None) -> DocumentSet:
    """One generation call. `repair` is the failure feedback on a retry."""
    user = "\n\n".join(filter(None, [
        posting_block(posting.body, posting.employer, posting.title, posting.questions),
        TASK_DIRECTIVE,
        repair,
    ]))
    return structured_call(
        client,
        model=model,
        max_tokens=max_tokens,
        system=system_blocks(profile, track),
        messages=[{"role": "user", "content": user}],
        output_format=DocumentSet,
        tally=tally,
        effort=effort,
    )


def generate_application(
    client: Client,
    posting: Posting,
    profile: Profile,
    *,
    track: Track | None = None,
    model: str = DEFAULT_MODEL,
    verify_model: str = DEFAULT_VERIFY_MODEL,
    max_tokens: int = GENERATION_MAX_TOKENS,
    max_attempts: int = 2,
    verify_entailment: bool = True,
    sources_path: Path | str | None = None,
    effort: str | None = None,
    verdicts: EntailmentCache | None = None,
) -> GenerationOutcome:
    """
    Produce a checked application, or park it.

    `max_attempts` is 2 per docs/04: one draft, one repair. Raising it trades
    money for a slightly better pass rate; it does not weaken any check, since
    every attempt faces the same gate.

    `verify_entailment=False` skips Layer 3 — useful for cheap iteration on
    prompts and formatting, and never appropriate for a document that will be
    sent. The outcome records that it was skipped by carrying an empty
    `entailment` list, so a caller cannot mistake "skipped" for "verified".

    `effort` is the cost lever that matters. 83% of a generation's bill is
    output tokens, and thinking counts against them — so the depth of thinking,
    not the size of the prompt, is what a run costs. Left unset it takes the
    model's default. Nothing about the checks changes at any setting: a cheaper
    draft that overstates something is caught and parked exactly as an
    expensive one would be, which is what makes this safe to sweep.

    `verdicts` lets a caller share the entailment cache across postings. CV
    bullets are near-identical from one posting to the next — the same role,
    the same evidence, often the same sentence — and a verdict is keyed on the
    exact text and the exact ids it cites, so a shared cache re-asks nothing
    and pays for each distinct sentence once per batch rather than once per
    application. Pass None to keep each application isolated.
    """
    if max_attempts < 1:
        raise GenerationError("max_attempts must be at least 1")

    track = track or choose_track(posting, sources_path=sources_path)

    repair: str | None = None
    last_audit: AuditResult | None = None
    last_ent: list[EntailmentResult] = []
    last_app: Application | None = None
    reason = ""
    tally = UsageTally()
    # Verdicts survive across attempts, keyed on the exact sentence and the
    # exact ids it cites. The repair turn is told to keep every line that
    # passed, so most of a second attempt's verification would otherwise be
    # re-asking questions already answered. A caller may pass one in to
    # share it across postings too.
    if verdicts is None:
        verdicts = {}

    for attempt in range(1, max_attempts + 1):
        docs = _draft(client, posting, profile, track, model=model,
                      max_tokens=max_tokens, repair=repair, tally=tally,
                      effort=effort)
        app = Application(
            posting_id=posting.posting_id,
            posting_title=posting.title,
            employer=posting.employer,
            track=track,
            cv=docs.cv,
            letter=docs.letter,
        )
        last_app, last_ent = app, []

        last_audit = audit(app, profile, posting_text=posting.body)
        if last_audit.blocked:
            reason = f"{len(last_audit.blocks)} blocking audit finding(s)"
            repair = retry_block(
                docs.model_dump_json(indent=2),
                [str(f) for f in last_audit.blocks],
                [],
            )
            continue

        if verify_entailment:
            last_ent = verify_application(client, app, profile,
                                          model=verify_model, tally=tally,
                                          cache=verdicts)
            bad = entailment_failures(last_ent)
            if bad:
                reason = f"{len(bad)} claim(s) not supported by cited evidence"
                repair = retry_block(docs.model_dump_json(indent=2), [],
                                     [str(r) for r in bad])
                continue

        return GenerationOutcome(
            posting=posting, track=track, status="ready", application=app,
            audit=last_audit, entailment=last_ent, attempts=attempt, usage=tally,
        )

    return GenerationOutcome(
        posting=posting, track=track, status="parked", application=last_app,
        audit=last_audit, entailment=last_ent, attempts=max_attempts, usage=tally,
        parked_reason=f"{reason} after {max_attempts} attempt(s) — held for human review",
    )


# --------------------------------------------------------------------------- #
# Rendering — the last gate
# --------------------------------------------------------------------------- #

def finalise(outcome: GenerationOutcome, profile: Profile, out_dir: Path | str,
             *, pdf: bool = True) -> dict[str, Path]:
    """
    Render the DOCX pair, run the Layer 2 round-trip, and add PDF companions.

    Round-trip failure raises rather than returning a flag. A document that an
    ATS cannot parse arrives at the employer as an anonymous blob, and there is
    no version of "send it anyway" that is better than stopping.

    The PDFs are best-effort and deliberately cannot block: DOCX is the
    canonical artefact (docs/07 F-A), the PDF is a companion for a human who
    opens the attachment directly. A machine without LibreOffice still produces
    a complete, sendable application.

    Parked outcomes are rendered too — `render_parked` exists precisely so a
    human can read what failed — but they never come through this function,
    which is the send path.
    """
    from .render_docx import render_cover_letter, render_cv  # noqa: PLC0415
    from ..evaluate.ats_roundtrip import assert_roundtrip    # noqa: PLC0415

    if not outcome.ready:
        raise GenerationError(
            f"refusing to finalise a {outcome.status} application: "
            f"{outcome.parked_reason or 'checks did not pass'}")

    assert outcome.application is not None
    out_dir = Path(out_dir)
    stem = f"Gedeon-Nzemba-{outcome.posting.slug}"

    cv_path = render_cv(outcome.application.cv, profile, out_dir / f"{stem}-CV.docx")
    letter_path = render_cover_letter(
        outcome.application.letter, profile, outcome.posting.employer,
        out_dir / f"{stem}-Cover-Letter.docx")

    assert_roundtrip(cv_path, outcome.application.cv, profile)

    paths = {"cv": cv_path, "letter": letter_path}
    if pdf:
        from .render_pdf import page_count, pdf_available, render_pdf  # noqa: PLC0415

        if pdf_available():
            paths["cv_pdf"] = render_pdf(cv_path)
            paths["letter_pdf"] = render_pdf(letter_path)

            # Length is the one docs/08 rule that only rendering can settle —
            # no count of characters predicts where the page breaks. Checked
            # here because here is where a real page exists.
            pages = page_count(paths["cv_pdf"])
            limit = MAX_PAGES[outcome.track]
            if pages > limit:
                raise LayoutError(
                    f"CV is {pages} pages; {outcome.track} allows {limit} "
                    f"(docs/08 §1.5). The documents are on disk at "
                    f"{cv_path.parent} — shorten and regenerate rather than "
                    f"sending page two, which this employer will not read.")
    return paths


def render_parked(outcome: GenerationOutcome, profile: Profile,
                  out_dir: Path | str) -> dict[str, Path]:
    """
    Write a parked application to disk for human review, alongside its report.

    No round-trip assertion — the point is to see what the model produced, and a
    parked document is not going anywhere on its own.
    """
    from .render_docx import render_cover_letter, render_cv  # noqa: PLC0415

    if outcome.application is None:
        raise GenerationError("nothing to render — generation never produced a draft")

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"PARKED-{outcome.posting.slug}"

    paths = {
        "cv": render_cv(outcome.application.cv, profile, out_dir / f"{stem}-CV.docx"),
        "letter": render_cover_letter(
            outcome.application.letter, profile, outcome.posting.employer,
            out_dir / f"{stem}-Cover-Letter.docx"),
    }
    report = out_dir / f"{stem}-WHY-PARKED.txt"
    report.write_text(outcome.report() + "\n", encoding="utf-8")
    paths["report"] = report
    return paths


__all__ = ["Posting", "GenerationOutcome", "GenerationError", "Status",
           "generate_application", "choose_track", "finalise", "render_parked"]
