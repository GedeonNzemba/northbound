"""
Tests for the generator pipeline.

No network and no API key: a fake client returns canned drafts and canned
entailment verdicts, which lets every branch of the gate be tested — including
the ones that only happen when the model gets something wrong, which is exactly
where a real API would be least reproducible.

The property under test throughout is the same one: **nothing reaches "ready"
without passing every check.** Each test tries a different way to sneak past it.
"""

from __future__ import annotations

import re

import pytest
from fixtures import PROFILE, POSTING_BODY, cv, docset, full_cv

from northbound.generate.audit import screening_questions
from northbound.generate.entailment import EntailmentVerdict
from northbound.generate.generator import (
    GenerationError, Posting, choose_track, finalise, generate_application,
    render_parked,
)
from northbound.generate.llm import LLMError, RefusalError
from northbound.generate.prompts import render_profile_block, system_blocks
from northbound.generate.schemas import DocumentSet


# --------------------------------------------------------------------------- #
# Fake client
# --------------------------------------------------------------------------- #

class _Usage:
    """Mirrors the shape the SDK returns. Cache reads are the field that matters."""

    def __init__(self, cache_read=1000, cache_creation=0, inp=200, out=800):
        self.input_tokens = inp
        self.output_tokens = out
        self.cache_creation_input_tokens = cache_creation
        self.cache_read_input_tokens = cache_read


class _Resp:
    def __init__(self, parsed, stop_reason="end_turn", usage=None, stop_details=None):
        self.parsed_output = parsed
        self.stop_reason = stop_reason
        self.usage = usage if usage is not None else _Usage()
        self.stop_details = stop_details


class _FakeMessages:
    """
    Serves drafts in order, and a verdict per entailment call.

    Running out of drafts is an assertion failure rather than a repeat, so a
    test that expects one attempt cannot silently pass while the pipeline
    quietly retried.
    """

    def __init__(self, drafts, verdict_for=None):
        self.drafts = list(drafts)
        self.verdict_for = verdict_for or (lambda claim, source: EntailmentVerdict(verdict="supported"))
        self.calls: list[dict] = []

    def parse(self, **kw):
        self.calls.append(kw)
        fmt = kw["output_format"]
        if fmt is DocumentSet:
            if not self.drafts:
                raise AssertionError("generator requested more drafts than the test supplied")
            return _Resp(self.drafts.pop(0))
        if fmt is EntailmentVerdict:
            content = kw["messages"][0]["content"]
            source, claim = re.match(r"SOURCE:\n(.*)\n\nCLAIM:\n(.*)", content, re.S).groups()
            return _Resp(self.verdict_for(claim, source))
        raise AssertionError(f"unexpected output_format {fmt!r}")

    # ---- inspection helpers ---------------------------------------------- #
    @property
    def draft_calls(self) -> list[dict]:
        return [c for c in self.calls if c["output_format"] is DocumentSet]

    @property
    def verify_calls(self) -> list[dict]:
        return [c for c in self.calls if c["output_format"] is EntailmentVerdict]

    def prompt(self, n: int) -> str:
        return self.draft_calls[n]["messages"][0]["content"]


class FakeClient:
    def __init__(self, drafts, verdict_for=None):
        self.messages = _FakeMessages(drafts, verdict_for)


FARM = Posting(
    posting_id="49816590",
    title="general labourer - farm",
    employer="Ridge Farms",
    body=POSTING_BODY,
    location="Leamington, Ontario",
    noc="85101",
    queue="lmia_approved",
)

DEV = Posting(
    posting_id="49900001",
    title="front end developer",
    employer="Northwind Digital",
    body="We are hiring a front end developer to work in React and TypeScript.",
    location="Toronto, Ontario",
    noc="21234",
    queue="international_candidates",
)


def _overstate(needle: str, span: str):
    """A verdict function that fails exactly one claim."""
    def verdict_for(claim: str, source: str) -> EntailmentVerdict:
        if needle in claim:
            return EntailmentVerdict(verdict="overstated", offending_span=span,
                                     reason="the source does not state this")
        return EntailmentVerdict(verdict="supported")
    return verdict_for


# --------------------------------------------------------------------------- #
# The happy path and the gate
# --------------------------------------------------------------------------- #

def test_clean_draft_is_ready_on_first_attempt():
    client = FakeClient([docset()])
    out = generate_application(client, FARM, PROFILE)
    assert out.ready and out.status == "ready"
    assert out.attempts == 1
    assert len(client.messages.draft_calls) == 1
    assert out.entailment and all(r.ok for r in out.entailment)


def test_audit_failure_is_repaired_on_retry():
    bad = docset(cv_=cv(summary_evidence_ids=["gen.does.not.exist"]))
    client = FakeClient([bad, docset()])
    out = generate_application(client, FARM, PROFILE)

    assert out.ready, out.report()
    assert out.attempts == 2
    assert len(client.messages.draft_calls) == 2


def test_the_repair_prompt_carries_the_previous_draft_and_the_exact_failure():
    """Targeted correction, not a blind resample — docs/04."""
    bad = docset(cv_=cv(summary_evidence_ids=["gen.does.not.exist"]))
    client = FakeClient([bad, docset()])
    generate_application(client, FARM, PROFILE)

    first, second = client.messages.prompt(0), client.messages.prompt(1)
    assert "REJECTED" not in first, "the first attempt must not carry repair text"
    assert "REJECTED" in second
    assert "gen.does.not.exist" in second, "the failing id must be named"
    assert "evidence.unknown" in second, "the rule that fired must be named"
    assert "General Farm Worker" in second, "the previous draft must be shown back"


def test_a_second_failure_parks_and_is_never_ready():
    bad = docset(cv_=cv(summary_evidence_ids=["gen.does.not.exist"]))
    client = FakeClient([bad, bad])
    out = generate_application(client, FARM, PROFILE)

    assert out.status == "parked"
    assert out.ready is False
    assert out.application is not None, "a parked application still exists for review"
    assert "audit" in out.parked_reason
    assert "human review" in out.parked_reason


def test_excluded_evidence_cannot_reach_ready():
    """gen.packer.h4 is verify: true — exclusion is the default (docs/04)."""
    bad = docset(cv_=cv(summary_evidence_ids=["gen.packer.h4"]))
    client = FakeClient([bad, bad])
    out = generate_application(client, FARM, PROFILE)
    assert out.status == "parked"
    assert any(f.rule == "evidence.excluded" for f in out.audit.blocks)


def test_max_attempts_one_never_retries():
    bad = docset(cv_=cv(summary_evidence_ids=["gen.does.not.exist"]))
    client = FakeClient([bad])
    out = generate_application(client, FARM, PROFILE, max_attempts=1)
    assert out.status == "parked"
    assert len(client.messages.draft_calls) == 1


def test_max_attempts_zero_is_rejected():
    with pytest.raises(GenerationError):
        generate_application(FakeClient([]), FARM, PROFILE, max_attempts=0)


# --------------------------------------------------------------------------- #
# Layer 3 — entailment
# --------------------------------------------------------------------------- #

def test_an_overstated_claim_parks_even_though_the_audit_passed():
    """
    The whole reason Layer 3 exists: the bullet cites a real id, every structural
    check passes, and it still says more than the source does.
    """
    client = FakeClient([docset(), docset()],
                        verdict_for=_overstate("Assisted qualified electricians",
                                               "qualified electricians"))
    out = generate_application(client, FARM, PROFILE)

    assert out.audit is not None and not out.audit.blocked, "the audit was clean"
    assert out.status == "parked"
    assert "not supported by cited evidence" in out.parked_reason
    assert any(not r.ok for r in out.entailment)


def test_the_offending_span_is_fed_back_on_the_retry():
    client = FakeClient([docset(), docset()],
                        verdict_for=_overstate("Assisted qualified electricians",
                                               "qualified electricians"))
    generate_application(client, FARM, PROFILE)
    second = client.messages.prompt(1)
    assert "not supported by the evidence" in second
    assert "qualified electricians" in second, "the span must be named for a targeted fix"


def test_an_entailment_failure_can_be_repaired():
    fixed = docset(cv_=cv())
    fixed.cv.experience[0].bullets[0].text = "Assisted electricians on estate construction sites."
    client = FakeClient([docset(), fixed],
                        verdict_for=_overstate("Assisted qualified electricians",
                                               "qualified electricians"))
    out = generate_application(client, FARM, PROFILE)
    assert out.ready, out.report()
    assert out.attempts == 2


def test_every_bullet_is_verified_in_isolation():
    """Context isolation — the verifier must see only the source and the claim."""
    client = FakeClient([docset()])
    generate_application(client, FARM, PROFILE)

    assert client.messages.verify_calls, "no claims were verified at all"
    for call in client.messages.verify_calls:
        content = call["messages"][0]["content"]
        assert content.startswith("SOURCE:")
        assert "Ridge Farms" not in content, "the posting must not leak into the verifier"
        assert "PROFILE" not in content, "the whole profile must not leak into the verifier"


def test_skipping_entailment_makes_no_verifier_calls():
    client = FakeClient([docset()])
    out = generate_application(client, FARM, PROFILE, verify_entailment=False)
    assert out.ready
    assert client.messages.verify_calls == []
    assert out.entailment == [], "skipped must not look like verified"


# --------------------------------------------------------------------------- #
# What the model is shown
# --------------------------------------------------------------------------- #

def test_screening_questions_reach_the_prompt_exactly_as_the_audit_reads_them():
    """
    Prompt and audit share one extractor, so a document can never be blocked for
    ignoring a question it was never shown.
    """
    client = FakeClient([docset()])
    generate_application(client, FARM, PROFILE)
    prompt = client.messages.prompt(0)

    qs = screening_questions(POSTING_BODY)
    assert qs, "the fixture posting is supposed to ask something"
    for q in qs:
        assert q in prompt


def test_excluded_evidence_is_never_shown_to_the_model():
    """It cannot cite what it has never seen — stronger than a warning."""
    block = render_profile_block(PROFILE)
    assert "gen.packer.h4" not in block
    assert "gen.cumpsty.h1" in block, "usable evidence must be present"


def test_the_cached_prefix_is_byte_stable():
    """A timestamp in the cached block would invalidate the cache every call."""
    assert render_profile_block(PROFILE) == render_profile_block(PROFILE)


def test_only_the_last_system_block_carries_the_cache_breakpoint():
    blocks = system_blocks(PROFILE, "transferable")
    assert [("cache_control" in b) for b in blocks] == [False, False, True]


def test_track_guidance_differs_by_track():
    b = system_blocks(PROFILE, "transferable")[1]["text"]
    a = system_blocks(PROFILE, "direct")[1]["text"]
    assert "TRANSFERABLE" in b and "DIRECT" in a


# --------------------------------------------------------------------------- #
# Track selection — D6 decides whether to apply, occupation decides the document
# --------------------------------------------------------------------------- #

def test_developer_posting_gets_track_a():
    assert choose_track(DEV) == "direct"


def test_farm_posting_gets_track_b():
    assert choose_track(FARM) == "transferable"


def test_a_tech_noc_wins_even_with_an_unhelpful_title():
    p = Posting(posting_id="x", title="IT specialist", employer="X", body="", noc="21234")
    assert choose_track(p) == "direct"


def test_a_tech_role_inside_the_lmia_queue_still_gets_track_a():
    """
    The LMIA queue defaults to transferable, but the sweep found two tech roles
    in it. Occupation decides the document, not the queue.
    """
    p = Posting(posting_id="x", title="web developer", employer="X", body="",
                queue="lmia_approved")
    assert choose_track(p) == "direct"


# --------------------------------------------------------------------------- #
# Rendering — the last gate
# --------------------------------------------------------------------------- #

def test_finalise_renders_both_documents_and_passes_the_roundtrip(tmp_path):
    client = FakeClient([docset(cv_=full_cv())])
    out = generate_application(client, FARM, PROFILE)
    paths = finalise(out, PROFILE, tmp_path)

    assert paths["cv"].exists() and paths["letter"].exists()
    assert "Ridge-Farms" in paths["cv"].name
    assert paths["cv"].name.endswith("-CV.docx")
    assert paths["letter"].name.endswith("-Cover-Letter.docx")


def test_a_parked_application_cannot_be_finalised(tmp_path):
    bad = docset(cv_=cv(summary_evidence_ids=["gen.does.not.exist"]))
    out = generate_application(FakeClient([bad, bad]), FARM, PROFILE)
    with pytest.raises(GenerationError, match="parked"):
        finalise(out, PROFILE, tmp_path)


# --------------------------------------------------------------------------- #
# SDK surface — the failures that only show up against the real API
# --------------------------------------------------------------------------- #

def test_a_refusal_is_raised_as_its_own_error_not_a_parse_failure():
    """Retrying a declined prompt fails the same way — the remedy differs."""
    class Refusing:
        messages = type("M", (), {
            "parse": staticmethod(lambda **kw: _Resp(
                None, stop_reason="refusal",
                stop_details=type("D", (), {"category": "cyber"})())),
        })()

    with pytest.raises(RefusalError, match="cyber"):
        generate_application(Refusing(), FARM, PROFILE)


def test_truncation_names_max_tokens_and_says_thinking_counts():
    """
    claude-opus-5 thinks by default and thinking counts against max_tokens, so
    a limit sized around the JSON alone truncates. The error has to say that.
    """
    class Truncating:
        messages = type("M", (), {
            "parse": staticmethod(lambda **kw: _Resp(None, stop_reason="max_tokens")),
        })()

    with pytest.raises(LLMError) as exc:
        generate_application(Truncating(), FARM, PROFILE)
    assert "max_tokens" in str(exc.value) and "thinking" in str(exc.value)


def test_usage_is_tallied_across_generation_and_verification():
    client = FakeClient([docset()])
    out = generate_application(client, FARM, PROFILE)

    assert out.usage.calls == len(client.messages.calls)
    assert out.usage.calls > 1, "generation plus per-claim verification"
    assert out.usage.total_prompt_tokens == (
        out.usage.input_tokens + out.usage.cache_creation_input_tokens
        + out.usage.cache_read_input_tokens)
    assert "cached" in out.report()


def test_zero_cache_reads_across_calls_is_surfaced_as_a_warning():
    """
    The cached prefix is byte-stable by construction — but construction is an
    argument, not a measurement. Zero reads means something is invalidating it.
    """
    client = FakeClient([docset()])
    original = client.messages.parse

    def parse_without_cache_hits(**kw):
        resp = original(**kw)
        resp.usage = _Usage(cache_read=0, cache_creation=0)
        return resp

    client.messages.parse = parse_without_cache_hits
    out = generate_application(client, FARM, PROFILE)
    assert "zero cache reads" in out.report()


def test_render_parked_writes_the_documents_and_says_why(tmp_path):
    bad = docset(cv_=cv(summary_evidence_ids=["gen.does.not.exist"]))
    out = generate_application(FakeClient([bad, bad]), FARM, PROFILE)
    paths = render_parked(out, PROFILE, tmp_path)

    assert paths["cv"].exists() and paths["letter"].exists()
    assert paths["cv"].name.startswith("PARKED-")
    why = paths["report"].read_text()
    assert "PARKED" in why and "gen.does.not.exist" in why
