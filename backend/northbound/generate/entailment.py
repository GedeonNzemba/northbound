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
  • **Context isolation.** The verifier sees the cited source entries and the
    generated line and nothing else — no posting, no CV, no track. Any of those
    would pull it toward agreeing, because the generated line will always look
    reasonable in the context that produced it.
  • **All cited sources at once.** A claim site is checked against everything it
    cites, together. The first live batch failed 11 truthful paragraphs because
    this module used to show the verifier one source at a time and ask whether
    that one covered the whole paragraph — a summary drawing honestly on four
    roles cannot pass such a test, and no amount of rewriting would have fixed
    it. Isolation is about withholding *context*, not about withholding the
    evidence the sentence actually rests on.
  • **Span-level output.** It must name the words that go beyond the sources, so
    a retry is targeted rather than a blind regenerate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

from pydantic import BaseModel, Field

from ..profile import Profile
from .llm import (
    DEFAULT_VERIFY_MODEL, VERIFY_MAX_TOKENS, Client, UsageTally,
    structured_call,
)
from .schemas import Application, CoverLetter, GeneratedCV

Verdict = Literal["supported", "overstated", "unsupported"]

VERIFIER_SYSTEM = """\
You verify one piece of text against the source records it cites. Nothing else.

You will be shown SOURCES (one or more factual records of things a person did) \
and a CLAIM (text written about them for a job application).

Decide whether the SOURCES, TAKEN TOGETHER, support the CLAIM:

- "supported"   — everything the CLAIM asserts is present in, or directly \
implied by, the SOURCES read as a set. Re-wording, condensing, re-ordering, \
changing tense and combining several sources into one sentence are all fine. \
Framing the same facts for a different audience is fine.
- "overstated"  — the CLAIM is about the same facts but asserts more than the \
SOURCES do: more skill, more seniority, more scale, more duration, more \
certainty, or a qualification the SOURCES do not state.
- "unsupported" — the CLAIM asserts something none of the SOURCES contains.

Be strict about these specifically, because they are the failure modes that \
matter here:
- A certification, licence or accreditation the SOURCES do not state. Having \
DONE something is not being CERTIFIED in it.
- Numbers, durations, team sizes or scale not in the SOURCES.
- Seniority or responsibility the SOURCES do not give (led, managed, owned, \
supervised, designed).
- Independence the SOURCES do not give — if a SOURCE says "assisted" or "under \
supervision", a CLAIM of doing it alone is overstated.
- Physical detail the SOURCES do not give. "Trenching and excavation" does not \
license "bending, kneeling and swinging hand tools for full days" — the posture, \
the tools and the duration are three separate assertions and each needs a source.

Do NOT penalise: ordinary re-wording, industry-standard vocabulary for the same \
activity, omitting detail, or making the same facts sound competent. Do NOT \
penalise a sentence for drawing on several SOURCES at once — that is what a \
multi-source CLAIM is for. Do NOT require any single SOURCE to cover the whole \
CLAIM on its own.

Statements about the writer's intentions, availability or willingness — "I will \
take that training", "I have never done this work", "available from May" — are \
not claims about the past and are not your concern. Ignore them and judge only \
the assertions of fact about what the person has done.

If the verdict is not "supported", quote the exact words of the CLAIM that go \
beyond the SOURCES.
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
    evidence_ids: tuple[str, ...]
    where: str

    @property
    def cited(self) -> str:
        return ", ".join(self.evidence_ids) or "—"


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
            return f"ok    [{self.claim.cited}] {self.claim.text[:60]}"
        sources = "\n".join(f"                {line}"
                            for line in self.source_text.splitlines())
        return (f"{self.verdict.upper()} [{self.claim.cited}] {self.claim.where}\n"
                f"        claim : {self.claim.text}\n"
                f"        source:\n{sources}\n"
                f"        span  : {self.offending_span!r} — {self.reason}")


def collect_claims(app: Application) -> list[Claim]:
    """
    Every piece of text that asserts something about Gedeon, with its citations.

    One entry per claim site, not one per citation. A bullet, the summary and
    each letter paragraph are each verified once, against the whole set of
    sources they name.
    """
    cv, letter = app.cv, app.letter
    claims: list[Claim] = []

    for e in list(cv.experience) + list(cv.additional_experience):
        for b in e.bullets:
            claims.append(Claim(b.text, tuple(b.evidence_ids),
                                f"cv.experience[{e.role_id}]"))

    claims.append(Claim(cv.summary, tuple(cv.summary_evidence_ids), "cv.summary"))
    claims.append(Claim(letter.evidence, tuple(letter.evidence_ids), "letter.evidence"))
    claims.append(Claim(letter.bridge, tuple(letter.bridge_evidence_ids), "letter.bridge"))

    return [c for c in claims if c.text.strip()]


def verify_claim(client: Client, claim: Claim, sources: list[str], *,
                 model: str = DEFAULT_VERIFY_MODEL,
                 tally: UsageTally | None = None) -> EntailmentResult:
    """
    One isolated call. The verifier gets the cited sources and the claim, and
    nothing else — no posting, no CV, no track.

    All of the sources, together. Showing them one at a time was the single
    biggest source of false failures in the first live batch: a summary that
    honestly synthesises four roles cannot be entailed by any one of them, so
    every such paragraph failed no matter how truthful it was. The verifier now
    sees what the writer saw.

    Low effort deliberately: this is a narrow, well-specified judgement made
    once per claim site, and keeping it cheap is what makes it affordable. The
    token limit still has to cover thinking, which is on by default — the
    verdict itself is three short fields.
    """
    block = "\n\n".join(f"[{i}] {s}" for i, s in enumerate(sources, 1))
    v = structured_call(
        client,
        model=model,
        max_tokens=VERIFY_MAX_TOKENS,
        system=VERIFIER_SYSTEM,
        effort="low",
        tally=tally,
        messages=[{
            "role": "user",
            "content": f"SOURCES:\n{block}\n\nCLAIM:\n{claim.text}",
        }],
        output_format=EntailmentVerdict,
    )
    return EntailmentResult(
        claim=claim, verdict=v.verdict, offending_span=v.offending_span,
        reason=v.reason, source_text=block,
    )


Cache = dict[tuple[str, tuple[str, ...]], EntailmentResult]


def verify_application(client: Client, app: Application, profile: Profile, *,
                       model: str = DEFAULT_VERIFY_MODEL,
                       tally: UsageTally | None = None,
                       cache: Cache | None = None) -> list[EntailmentResult]:
    """
    Verify every claim site once, against everything it cites.

    One call per claim site rather than one per citation. That is both the
    correct semantics — a sentence is honest if the records it names support it
    between them — and cheaper than the per-citation loop it replaces, which
    spent a call on each id of every multi-cited paragraph.

    Nothing about strictness changes. A sentence asserting something none of its
    sources contains still fails, and now it fails for a reason the model can
    act on: the span it must cut, rather than "source 3 of 5 didn't cover the
    whole paragraph".

    `cache` is keyed on the exact sentence and the exact ids it cites, so it
    only ever returns a verdict for text that has not changed at all. A repair
    turn is told to keep every line that passed, and most of them do — so most
    of a second attempt's verification is a re-run of calls whose answer is
    already known. Passing a dict across attempts is what stops paying for them
    twice.
    """
    out: list[EntailmentResult] = []
    for claim in collect_claims(app):
        key = (claim.text, claim.evidence_ids)
        if cache is not None and key in cache:
            out.append(cache[key])
            continue
        res = _verify_one(client, claim, profile, model, tally)
        if cache is not None:
            cache[key] = res
        out.append(res)
    return out


def _verify_one(client: Client, claim: Claim, profile: Profile,
                model: str, tally: UsageTally | None) -> EntailmentResult:
    missing = [i for i in claim.evidence_ids if profile.evidence.get(i) is None]
    if missing:
        return EntailmentResult(
            claim=claim, verdict="unsupported", source_text="",
            reason=f"evidence id(s) do not exist: {', '.join(missing)}")
    sources = [profile.evidence[i].text for i in claim.evidence_ids]
    if not sources:
        return EntailmentResult(claim=claim, verdict="unsupported", source_text="",
                                reason="cites no evidence at all")
    return verify_claim(client, claim, sources, model=model, tally=tally)


def failures(results: Iterable[EntailmentResult]) -> list[EntailmentResult]:
    return [r for r in results if not r.ok]


def report(results: list[EntailmentResult]) -> str:
    bad = failures(results)
    head = (f"ENTAILMENT: {len(results) - len(bad)}/{len(results)} supported"
            + ("" if not bad else f" — {len(bad)} BLOCKING"))
    return "\n".join([head, *(str(r) for r in results)])


__all__ = ["verify_application", "verify_claim", "collect_claims", "Cache",
           "Claim", "EntailmentResult", "EntailmentVerdict", "failures", "report"]
