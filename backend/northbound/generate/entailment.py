"""
The entailment pass — docs/04 rule 6, docs/07 F-E.

Structural checks verify that a bullet *cites* something. They do not verify that
the citation *supports* it. Those are different properties, and the gap between
them is exactly where a CV becomes a misrepresentation.

The worked case: the generator cites `gen.painter.h2` — "Worked at height in full
body protection / fall-arrest harness on multi-storey buildings" — and writes
"Certified in fall-arrest systems." Real id, real underlying experience, every
structural check passes, and it is false in a way a work-permit officer can treat
as misrepresentation.

Design decisions that matter:

  • **Claim level, not document level.** Fact-level verification outperforms
    whole-document scoring in the literature, and it tells you WHICH line to fix.
  • **Context isolation.** The verifier sees the source entry and the generated
    line and nothing else — no posting, no CV, no track. Any of those would pull
    it toward agreeing, because the generated line will always look reasonable
    in the context that produced it.
  • **Span-level output.** It must name the words that go beyond the source, so
    a retry is targeted rather than a blind regenerate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

from pydantic import BaseModel, Field

from ..profile import Profile
from .llm import (
    DEFAULT_MODEL, VERIFY_MAX_TOKENS, Client, UsageTally, structured_call,
)
from .schemas import Application, CoverLetter, GeneratedCV

Verdict = Literal["supported", "overstated", "unsupported"]

VERIFIER_SYSTEM = """\
You verify one sentence against one source statement. Nothing else.

You will be shown a SOURCE (a factual record of something a person did) and a \
CLAIM (a sentence written about it for a job application).

Decide whether the SOURCE supports the CLAIM:

- "supported"   — everything the CLAIM asserts is present in or directly implied \
by the SOURCE. Re-wording, condensing, re-ordering and changing tense are all \
fine. Framing the same fact for a different audience is fine.
- "overstated"  — the CLAIM is about the same fact but asserts more than the \
SOURCE does: more skill, more seniority, more scale, more duration, more \
certainty, or a qualification the SOURCE does not state.
- "unsupported" — the CLAIM asserts something the SOURCE does not contain at all.

Be strict about these specifically, because they are the failure modes that \
matter here:
- A certification, licence or accreditation that the SOURCE does not state. \
Having DONE something is not being CERTIFIED in it.
- Numbers, durations, team sizes or scale not in the SOURCE.
- Seniority or responsibility the SOURCE does not give (led, managed, owned, \
supervised, designed).
- Independence the SOURCE does not give — if the SOURCE says "assisted" or \
"under supervision", a CLAIM of doing it alone is overstated.

Do NOT penalise: ordinary re-wording, industry-standard vocabulary for the same \
activity, omitting detail, or making the same fact sound competent.

If the verdict is not "supported", quote the exact words of the CLAIM that go \
beyond the SOURCE.
"""


class EntailmentVerdict(BaseModel):
    verdict: Verdict = Field(description="supported | overstated | unsupported")
    offending_span: str = Field(
        default="",
        description="Exact words from the CLAIM that go beyond the SOURCE. Empty if supported.")
    reason: str = Field(default="", description="One sentence. Empty if supported.")


@dataclass(frozen=True)
class Claim:
    text: str
    evidence_id: str
    where: str


@dataclass
class EntailmentResult:
    claim: Claim
    verdict: Verdict
    offending_span: str = ""
    reason: str = ""
    source_text: str = ""

    @property
    def ok(self) -> bool:
        return self.verdict == "supported"

    def __str__(self) -> str:
        if self.ok:
            return f"ok    [{self.claim.evidence_id}] {self.claim.text[:60]}"
        return (f"{self.verdict.upper()} [{self.claim.evidence_id}] {self.claim.where}\n"
                f"        claim : {self.claim.text}\n"
                f"        source: {self.source_text}\n"
                f"        span  : {self.offending_span!r} — {self.reason}")


def collect_claims(app: Application) -> list[Claim]:
    """Every sentence that asserts something about Gedeon, with its citation."""
    cv, letter = app.cv, app.letter
    claims: list[Claim] = []

    for e in list(cv.experience) + list(cv.additional_experience):
        for b in e.bullets:
            claims.append(Claim(b.text, b.evidence_id, f"cv.experience[{e.role_id}]"))

    # The summary and letter paragraphs cite a SET of ids, so each is verified
    # against each cited source. A paragraph is supported only if some source
    # supports it — checked by the caller via `any`.
    for ev_id in cv.summary_evidence_ids:
        claims.append(Claim(cv.summary, ev_id, "cv.summary"))
    for ev_id in letter.evidence_ids:
        claims.append(Claim(letter.evidence, ev_id, "letter.evidence"))
    for ev_id in letter.bridge_evidence_ids:
        claims.append(Claim(letter.bridge, ev_id, "letter.bridge"))

    return claims


def verify_claim(client: Client, claim: Claim, source_text: str, *,
                 model: str = DEFAULT_MODEL,
                 tally: UsageTally | None = None) -> EntailmentResult:
    """
    One isolated call. The verifier gets the source and the claim — nothing else.

    Low effort deliberately: this is a narrow, well-specified judgement, and
    keeping it cheap is what makes per-bullet verification affordable. The token
    limit still has to cover thinking, which is on by default — the verdict
    itself is three short fields.
    """
    v = structured_call(
        client,
        model=model,
        max_tokens=VERIFY_MAX_TOKENS,
        system=VERIFIER_SYSTEM,
        effort="low",
        tally=tally,
        messages=[{
            "role": "user",
            "content": f"SOURCE:\n{source_text}\n\nCLAIM:\n{claim.text}",
        }],
        output_format=EntailmentVerdict,
    )
    return EntailmentResult(
        claim=claim, verdict=v.verdict, offending_span=v.offending_span,
        reason=v.reason, source_text=source_text,
    )


def verify_application(client: Client, app: Application, profile: Profile, *,
                       model: str = DEFAULT_MODEL,
                       tally: UsageTally | None = None) -> list[EntailmentResult]:
    """
    Verify every claim. Returns all results; the caller decides what blocks.

    Multi-cited text (summary, letter paragraphs) is grouped: it passes if ANY
    of its cited sources supports it, because a paragraph drawing on three
    entries is not overstating merely because one of them alone doesn't cover it.
    """
    results: list[EntailmentResult] = []
    grouped: dict[tuple[str, str], list[EntailmentResult]] = {}

    for claim in collect_claims(app):
        ev = profile.evidence.get(claim.evidence_id)
        if ev is None:
            results.append(EntailmentResult(
                claim=claim, verdict="unsupported",
                reason="evidence id does not exist", source_text=""))
            continue

        res = verify_claim(client, claim, ev.text, model=model, tally=tally)
        if claim.where in ("cv.summary", "letter.evidence", "letter.bridge"):
            grouped.setdefault((claim.where, claim.text), []).append(res)
        else:
            results.append(res)

    for (_where, _text), group in grouped.items():
        best = next((g for g in group if g.ok), None)
        results.append(best or group[0])

    return results


def failures(results: Iterable[EntailmentResult]) -> list[EntailmentResult]:
    return [r for r in results if not r.ok]


def report(results: list[EntailmentResult]) -> str:
    bad = failures(results)
    head = (f"ENTAILMENT: {len(results) - len(bad)}/{len(results)} supported"
            + ("" if not bad else f" — {len(bad)} BLOCKING"))
    return "\n".join([head, *(str(r) for r in results)])


__all__ = ["verify_application", "verify_claim", "collect_claims",
           "EntailmentResult", "EntailmentVerdict", "failures", "report"]
