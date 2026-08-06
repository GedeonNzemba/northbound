"""
The single seam onto the Anthropic SDK.

Every model call in the CV engine goes through `structured_call`. That is
deliberate: structured outputs are a fast-moving part of the SDK, and one
function is one place to fix if the surface shifts, rather than a search across
the generator and the entailment verifier.

It also makes the whole engine testable without a network or an API key — every
test passes a fake client with a `messages.parse` that returns canned objects.
"""

from __future__ import annotations

from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

DEFAULT_MODEL = "claude-opus-5"

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """The model returned nothing usable — refusal, truncation, or a parse failure."""


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
    max_tokens: int = 8000,
    effort: str | None = None,
) -> T:
    """
    One call, one typed object back.

    `effort` maps to `output_config`; the entailment verifier runs at "low"
    because it is a narrow judgement made thousands of times, while document
    generation leaves it unset and takes the model's default.
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
    parsed = getattr(resp, "parsed_output", None)
    if parsed is None:
        stop = getattr(resp, "stop_reason", "unknown")
        raise LLMError(
            f"no parsed output (stop_reason={stop!r}). If this is 'max_tokens', "
            "raise max_tokens; if 'refusal', the prompt tripped a safety filter."
        )
    return parsed


__all__ = ["structured_call", "default_client", "Client", "LLMError", "DEFAULT_MODEL"]
