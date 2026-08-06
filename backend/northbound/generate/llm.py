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

from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

DEFAULT_MODEL = "claude-opus-5"

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


@dataclass
class UsageTally:
    """
    Running token totals across a generation.

    Exists for one reason: `cache_read_input_tokens` is the only evidence that
    the cached profile prefix is actually working. It is large and byte-stable
    by construction, but "by construction" is an argument, not a measurement —
    if this stays at zero across a run, something is silently invalidating the
    prefix and every generation is paying full price for it.
    """

    calls: int = 0
    input_tokens: int = 0            # the uncached remainder only
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

    def record(self, resp: Any) -> None:
        u = getattr(resp, "usage", None)
        if u is None:
            return
        self.calls += 1
        for field in ("input_tokens", "output_tokens",
                      "cache_creation_input_tokens", "cache_read_input_tokens"):
            setattr(self, field, getattr(self, field) + (getattr(u, field, 0) or 0))

    @property
    def total_prompt_tokens(self) -> int:
        """Prompt size is the sum of all three — `input_tokens` is the remainder."""
        return (self.input_tokens + self.cache_creation_input_tokens
                + self.cache_read_input_tokens)

    def report(self) -> str:
        if not self.calls:
            return "usage: no model calls"
        cached = self.cache_read_input_tokens
        pct = (100 * cached / self.total_prompt_tokens) if self.total_prompt_tokens else 0
        line = (f"usage: {self.calls} call(s)  "
                f"prompt {self.total_prompt_tokens:,} "
                f"({cached:,} cached = {pct:.0f}%)  "
                f"output {self.output_tokens:,}")
        if self.calls > 1 and cached == 0:
            line += "\n  WARNING: zero cache reads across multiple calls — the "
            line += "profile prefix is being invalidated somewhere"
        return line


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
        tally.record(resp)

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
           "LLMError", "RefusalError", "DEFAULT_MODEL",
           "GENERATION_MAX_TOKENS", "VERIFY_MAX_TOKENS"]
