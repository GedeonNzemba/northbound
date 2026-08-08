"""
The single seam onto the Anthropic SDK.

Every model call in the CV engine goes through `structured_call`. That is
deliberate: structured outputs are a fast-moving part of the SDK, and one
function is one place to fix if the surface shifts, rather than a search across
the generator and the entailment verifier.

It also makes the whole engine testable without a network or an API key — every
test passes a fake client with a `messages.parse` that returns canned objects.

Two facts about claude-opus-5 shape the defaults here:

  • **Thinking is on by default**, and `max_tokens` caps thinking *plus* the
    response. A limit sized around the JSON alone truncates mid-document. The
    defaults below leave room for both.
  • **A request can be declined** (`stop_reason: "refusal"`, HTTP 200 with no
    parsed output). That is a distinct failure from a malformed response and is
    raised as such, because the remedy is different.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

DEFAULT_MODEL = "claude-opus-5"

# The verifier answers one narrow question — "does this source support this
# sentence?" — several hundred times a batch, and it is ~20 of every 21 calls.
# Generation is where document quality is decided and should stay on the best
# model available; verification is a different job and Haiku does it at a
# fifth of the price. Split so the expensive model is spent where it earns.
DEFAULT_VERIFY_MODEL = "claude-haiku-4-5"

# Sized for adaptive thinking, not for the JSON. See the module docstring.
GENERATION_MAX_TOKENS = 16000
VERIFY_MAX_TOKENS = 4000

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """The model returned nothing usable — truncation, or a parse failure."""


class RefusalError(LLMError):
    """
    The request was declined by a safety classifier.

    Separate from LLMError because the fix is different: retrying the same
    prompt will fail the same way. If this ever fires on a job posting — the
    plausible trigger being a posting whose text happens to touch a restricted
    topic — the remedy is the server-side `fallbacks` parameter, not a retry.
    """


# USD per million tokens, base input/output. Cache reads bill at 0.1x input and
# cache writes at 1.25x, which is why the cached profile prefix is worth the
# trouble: it is the difference between paying full price for ~5,000 tokens of
# profile on every posting and paying a tenth of it.
#
# The multipliers are applied rather than transcribed, because a hand-written
# cache_read of 0.50 next to an input of 5.00 is a number that can silently
# stop matching when the input price is edited.
#
# Prices do change. They are here to turn "how much did that cost?" into a
# printed line rather than a question — treat the number as a good estimate,
# and the invoice as the truth.
PRICE_PER_MTOK = {
    "claude-opus-5": {"input": 5.00, "output": 25.00},
    "claude-sonnet-5": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
}
CACHE_READ_MULTIPLIER = 0.1
CACHE_WRITE_MULTIPLIER = 1.25

# What an unknown model is priced at, so a new id shows a plausible number
# instead of $0.00 — which would read as "this was free".
FALLBACK_PRICE = PRICE_PER_MTOK["claude-opus-5"]


@dataclass
class ModelUsage:
    """Token totals for one model."""

    calls: int = 0
    input_tokens: int = 0            # the uncached remainder only
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

    FIELDS = ("calls", "input_tokens", "output_tokens",
              "cache_creation_input_tokens", "cache_read_input_tokens")

    @property
    def total_prompt_tokens(self) -> int:
        """Prompt size is the sum of all three — `input_tokens` is the remainder."""
        return (self.input_tokens + self.cache_creation_input_tokens
                + self.cache_read_input_tokens)

    def cost_usd(self, model: str) -> float:
        p = PRICE_PER_MTOK.get(model, FALLBACK_PRICE)
        return (self.input_tokens * p["input"]
                + self.output_tokens * p["output"]
                + self.cache_read_input_tokens * p["input"] * CACHE_READ_MULTIPLIER
                + self.cache_creation_input_tokens * p["input"] * CACHE_WRITE_MULTIPLIER
                ) / 1_000_000

    def cost_without_caching_usd(self, model: str) -> float:
        p = PRICE_PER_MTOK.get(model, FALLBACK_PRICE)
        return (self.total_prompt_tokens * p["input"]
                + self.output_tokens * p["output"]) / 1_000_000


@dataclass
class UsageTally:
    """
    Running token totals across a generation, kept per model.

    Per model because this engine deliberately runs two: the document is written
    by the best model available and the verifier — ~20 of every 21 calls — runs
    on Haiku at a fifth of the price. A single bucket priced at the generator's
    rate reports a batch as five times more expensive than it was, and the
    number it prints is the one the cost decisions get made on.

    The other reason this exists: `cache_read_input_tokens` is the only evidence
    that the cached profile prefix is actually working. It is large and
    byte-stable by construction, but "by construction" is an argument, not a
    measurement — if it stays at zero across a run, something is silently
    invalidating the prefix and every generation is paying full price for it.
    """

    by_model: dict[str, ModelUsage] = field(default_factory=dict)

    # ---- recording -------------------------------------------------------- #

    def record(self, resp: Any, model: str = "") -> None:
        u = getattr(resp, "usage", None)
        if u is None:
            return
        # The response says which model actually served the request, which is
        # the one that gets billed. The requested id is the fallback.
        served = getattr(resp, "model", None) or model or "unknown"
        m = self.by_model.setdefault(served, ModelUsage())
        m.calls += 1
        for f in ModelUsage.FIELDS[1:]:
            setattr(m, f, getattr(m, f) + (getattr(u, f, 0) or 0))

    def merge(self, other: UsageTally) -> None:
        """Fold another tally in, keeping the per-model split intact."""
        for model, usage in other.by_model.items():
            mine = self.by_model.setdefault(model, ModelUsage())
            for f in ModelUsage.FIELDS:
                setattr(mine, f, getattr(mine, f) + getattr(usage, f))

    # ---- aggregates ------------------------------------------------------- #

    def _sum(self, attr: str) -> int:
        return sum(getattr(m, attr) for m in self.by_model.values())

    @property
    def calls(self) -> int:
        return self._sum("calls")

    @property
    def input_tokens(self) -> int:
        return self._sum("input_tokens")

    @property
    def output_tokens(self) -> int:
        return self._sum("output_tokens")

    @property
    def cache_creation_input_tokens(self) -> int:
        return self._sum("cache_creation_input_tokens")

    @property
    def cache_read_input_tokens(self) -> int:
        return self._sum("cache_read_input_tokens")

    @property
    def total_prompt_tokens(self) -> int:
        return self._sum("total_prompt_tokens")

    @property
    def cost_usd(self) -> float:
        return sum(u.cost_usd(model) for model, u in self.by_model.items())

    @property
    def cost_without_caching_usd(self) -> float:
        return sum(u.cost_without_caching_usd(model)
                   for model, u in self.by_model.items())

    # ---- reporting -------------------------------------------------------- #

    def report(self) -> str:
        if not self.calls:
            return "usage: no model calls"
        cached = self.cache_read_input_tokens
        pct = (100 * cached / self.total_prompt_tokens) if self.total_prompt_tokens else 0
        saved = self.cost_without_caching_usd - self.cost_usd
        lines = [f"usage: {self.calls} call(s)  "
                 f"prompt {self.total_prompt_tokens:,} "
                 f"({cached:,} cached = {pct:.0f}%)  "
                 f"output {self.output_tokens:,}  "
                 f"≈ ${self.cost_usd:,.2f}"
                 + (f" (caching saved ${saved:,.2f})" if saved > 0.005 else "")]

        # The split is the point when two models are in play: it is the only
        # way to see that the expensive model is being spent where it earns.
        # It is also shown for a single model the price table does not know,
        # because the alternative is a confident number with no basis.
        unpriced = [m for m in self.by_model if m not in PRICE_PER_MTOK]
        if len(self.by_model) > 1 or unpriced:
            for model, u in sorted(self.by_model.items(),
                                   key=lambda kv: -kv[1].cost_usd(kv[0])):
                lines.append(f"  {model:<20} {u.calls:>4} call(s)  "
                             f"≈ ${u.cost_usd(model):,.2f}"
                             + ("" if model in PRICE_PER_MTOK
                                else "   (price unknown — estimated at opus rates)"))

        if self.calls > 1 and cached == 0:
            lines.append("  WARNING: zero cache reads across multiple calls — the "
                         "profile prefix is being invalidated somewhere")
        return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Which failures are worth continuing past, and which are not
# --------------------------------------------------------------------------- #

# Conditions that cannot change during a run. Every posting in a batch uses the
# same key, the same model and the same account, so once one of these comes back
# the rest will fail identically — and a batch that keeps going turns one clear
# problem into fifty lines of noise with a summary nobody can read.
#
# A run out of credit did exactly that: seventeen identical 400s, each printing
# the whole JSON body, and a table that said ERROR seventeen times.
#
# Classified structurally rather than by SDK exception class, because this
# module deliberately does not import `anthropic` — the engine and its tests run
# without it installed.
_FATAL_SIGNS: tuple[tuple[int | None, str, str], ...] = (
    (None, "credit balance is too low",
     "the account is out of API credit. Top it up at "
     "https://console.anthropic.com/settings/billing — the requests that failed "
     "were rejected before any tokens were used, so nothing was charged for them"),
    (401, "",
     "the API key was rejected. Check ANTHROPIC_API_KEY in .env — a stale or "
     "revoked key fails identically on every request"),
    (403, "",
     "the API key is not permitted to do this. Check which workspace it belongs "
     "to and what it is scoped to"),
    (404, "model",
     "the model id was not found. Check --model and --verify-model against the "
     "ids this account can actually reach"),
)


class FatalAPIError(RuntimeError):
    """
    A failure that will repeat identically on every remaining item.

    Carries the original exception so a caller wanting the raw detail still has
    it, and a `remedy`, which is the point — an error someone can act on beats
    an error they have to interpret.
    """

    def __init__(self, remedy: str, original: BaseException) -> None:
        super().__init__(remedy)
        self.remedy = remedy
        self.original = original


def api_message(exc: BaseException) -> str:
    """
    The API's own `message` where there is one, rather than the JSON blob.

    An SDK error stringifies to the entire response body. Printed once that is
    informative; printed once per posting it buries the run.
    """
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict) and err.get("message"):
            return str(err["message"])
    text = str(exc)
    if m := re.search(r"['\"]message['\"]:\s*(['\"])(.+?)\1", text):
        return m.group(2)
    return text


def fatal_reason(exc: BaseException) -> str | None:
    """The remedy, if this failure will repeat for every remaining item; else None."""
    status = getattr(exc, "status_code", None)
    message = api_message(exc).lower()
    for want_status, needle, remedy in _FATAL_SIGNS:
        if want_status is not None and status != want_status:
            continue
        if needle and needle not in message:
            continue
        if want_status is None and not needle:
            continue                    # a rule matching everything is a bug
        return remedy
    return None


class Client(Protocol):
    """Structural type for what this package needs from `anthropic.Anthropic`."""

    messages: Any


def default_client(api_key: str | None = None) -> Client:
    """
    Construct a real client. Imported lazily so the package — and its tests —
    work in an environment with no `anthropic` installed.
    """
    import anthropic  # noqa: PLC0415 — deliberate lazy import

    return anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()


def structured_call(
    client: Client,
    *,
    system: str | list[dict],
    messages: list[dict],
    output_format: type[T],
    model: str = DEFAULT_MODEL,
    max_tokens: int = GENERATION_MAX_TOKENS,
    effort: str | None = None,
    tally: UsageTally | None = None,
) -> T:
    """
    One call, one typed object back.

    `effort` maps to `output_config`. The entailment verifier asks for "low"
    because it is a narrow judgement made hundreds of times; document generation
    leaves it unset and takes the model's default.

    NOTE — the one unverified assumption in this file: `messages.parse()` derives
    `output_config.format` from `output_format`, so passing `output_config`
    alongside it relies on the SDK merging the two rather than replacing. If a
    first live run rejects that combination, drop the `effort` argument here;
    nothing else in the engine depends on it.
    """
    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": messages,
        "output_format": output_format,
    }
    if effort:
        kwargs["output_config"] = {"effort": effort}

    resp = client.messages.parse(**kwargs)
    if tally is not None:
        tally.record(resp, model)

    stop = getattr(resp, "stop_reason", "unknown")
    if stop == "refusal":
        detail = getattr(resp, "stop_details", None)
        category = getattr(detail, "category", None) if detail else None
        raise RefusalError(f"request declined (category={category!r})")

    parsed = getattr(resp, "parsed_output", None)
    if parsed is None:
        raise LLMError(
            f"no parsed output (stop_reason={stop!r}). If this is 'max_tokens', "
            f"raise max_tokens — thinking counts against it, so the limit must "
            f"cover reasoning as well as the document."
        )
    return parsed


__all__ = ["structured_call", "default_client", "Client", "UsageTally",
           "LLMError", "RefusalError", "FatalAPIError", "fatal_reason",
           "api_message", "ModelUsage", "DEFAULT_MODEL",
           "DEFAULT_VERIFY_MODEL", "PRICE_PER_MTOK",
           "GENERATION_MAX_TOKENS", "VERIFY_MAX_TOKENS",
           "CACHE_READ_MULTIPLIER", "CACHE_WRITE_MULTIPLIER"]
