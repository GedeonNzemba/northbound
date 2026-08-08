"""
Cost accounting.

The number this prints is the number cost decisions get made on, so it gets
tested like any other output. The bug it exists to prevent: pricing every call
at the generator's rate when ~20 of every 21 calls run on a model that costs a
fifth as much.
"""

from __future__ import annotations

from northbound.generate.llm import (
    CACHE_READ_MULTIPLIER, CACHE_WRITE_MULTIPLIER, PRICE_PER_MTOK, UsageTally,
)


class _Usage:
    def __init__(self, **kw):
        for f in ("input_tokens", "output_tokens",
                  "cache_creation_input_tokens", "cache_read_input_tokens"):
            setattr(self, f, kw.get(f, 0))


class _Resp:
    def __init__(self, model, **kw):
        self.model = model
        self.usage = _Usage(**kw)


def test_each_model_is_priced_at_its_own_rate():
    """
    The regression. One bucket priced at Opus rates reported the first live
    batch as roughly twice what the same run costs with the verifier on Haiku.
    """
    t = UsageTally()
    t.record(_Resp("claude-opus-5", input_tokens=1_000_000, output_tokens=1_000_000))
    t.record(_Resp("claude-haiku-4-5", input_tokens=1_000_000, output_tokens=1_000_000))

    assert t.cost_usd == 5.00 + 25.00 + 1.00 + 5.00
    assert t.calls == 2


def test_cache_rates_are_derived_from_the_input_price():
    t = UsageTally()
    t.record(_Resp("claude-sonnet-5",
                   cache_read_input_tokens=1_000_000,
                   cache_creation_input_tokens=1_000_000))
    inp = PRICE_PER_MTOK["claude-sonnet-5"]["input"]
    assert t.cost_usd == inp * CACHE_READ_MULTIPLIER + inp * CACHE_WRITE_MULTIPLIER


def test_an_unknown_model_is_priced_high_not_free():
    """A new id must never report $0.00 — that reads as 'this was free'."""
    t = UsageTally()
    t.record(_Resp("claude-something-new", input_tokens=1_000_000))
    assert t.cost_usd > 0
    assert "price unknown" in t.report()


def test_the_report_splits_by_model_so_the_expensive_one_is_visible():
    t = UsageTally()
    t.record(_Resp("claude-opus-5", input_tokens=10_000, output_tokens=5_000))
    for _ in range(20):
        t.record(_Resp("claude-haiku-4-5", input_tokens=1_200, output_tokens=300))

    report = t.report()
    assert "claude-opus-5" in report and "claude-haiku-4-5" in report
    assert report.index("claude-opus-5") < report.index("claude-haiku-4-5"), (
        "the costliest model must be listed first")
    assert "21 call(s)" in report


def test_merging_keeps_the_split():
    a, b = UsageTally(), UsageTally()
    a.record(_Resp("claude-opus-5", input_tokens=1_000))
    b.record(_Resp("claude-haiku-4-5", input_tokens=1_000))
    a.merge(b)
    assert set(a.by_model) == {"claude-opus-5", "claude-haiku-4-5"}
    assert a.calls == 2


def test_a_response_without_usage_is_not_counted():
    t = UsageTally()
    t.record(object())
    assert t.calls == 0
    assert t.report() == "usage: no model calls"
