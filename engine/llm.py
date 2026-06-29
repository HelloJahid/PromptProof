"""Thin model abstraction — the only place that knows about the LLM vendor.

The rest of the engine talks to `LLM`, never to the Anthropic SDK directly. The key
design move is the *injectable client*: `LLM(client=...)`. In production it builds a
real `AnthropicClient`; in tests you pass a `MockClient`, so the whole chain runs
offline with zero network calls and no API key. That single seam is what makes the
gates, retries, and feedback loop verifiable in CI.

Default model is `claude-sonnet-4-6` (cheap, fast, supports structured outputs); the
judge/evaluator can opt into `claude-opus-4-8` per call via the `model` argument.
Model IDs verified against live Anthropic docs (2026-06-27) — dateless pinned
snapshots, no date suffixes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable

# Default to the fast tier — these steps emit small, structured JSON, so Haiku is plenty and
# keeps live runs snappy. Override per call (CLI --model / GUI selector) for higher quality.
DEFAULT_MODEL = "claude-haiku-4-5"
JUDGE_MODEL = "claude-opus-4-8"

# Fail fast instead of the SDK's 10-minute default, so a stalled call surfaces as an error.
DEFAULT_TIMEOUT = 60.0


@dataclass
class LLMResponse:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = DEFAULT_MODEL


@runtime_checkable
class CompletionClient(Protocol):
    """Anything the LLM facade can call. Both AnthropicClient and MockClient satisfy it."""

    def complete(
        self, *, system: str, user: str, model: str, max_tokens: int
    ) -> LLMResponse: ...


class AnthropicClient:
    """Real client. Imports the SDK lazily so tests never need the package or a key."""

    def __init__(self, api_key: Optional[str] = None, *, timeout: float = DEFAULT_TIMEOUT):
        import anthropic  # lazy: keeps `import engine.llm` cheap and offline-friendly

        key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and fill it in."
            )
        self._client = anthropic.Anthropic(api_key=key, timeout=timeout)

    def complete(
        self, *, system: str, user: str, model: str, max_tokens: int
    ) -> LLMResponse:
        msg = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(
            block.text for block in msg.content if getattr(block, "type", None) == "text"
        )
        return LLMResponse(
            text=text,
            input_tokens=msg.usage.input_tokens,
            output_tokens=msg.usage.output_tokens,
            model=model,
        )


class MockClient:
    """Deterministic offline client for tests and demos. Never touches the network.

    Pass a list of scripted responses; each `complete` call pops the next one (or
    returns `default` once exhausted). Recorded calls are exposed on `.calls` so
    tests can assert on the prompts the engine produced.
    """

    def __init__(self, responses: Optional[list[str]] = None, default: str = "MOCK"):
        self._responses = list(responses or [])
        self._default = default
        self.calls: list[dict] = []

    def complete(
        self, *, system: str, user: str, model: str, max_tokens: int
    ) -> LLMResponse:
        self.calls.append(
            {"system": system, "user": user, "model": model, "max_tokens": max_tokens}
        )
        text = self._responses.pop(0) if self._responses else self._default
        # Rough token proxy keeps RunTrace meaningful offline without a tokenizer.
        return LLMResponse(
            text=text,
            input_tokens=len(user.split()),
            output_tokens=len(text.split()),
            model=model,
        )


class LLM:
    """Facade the engine uses. Builds a real client lazily if none is injected."""

    def __init__(
        self, client: Optional[CompletionClient] = None, *, model: str = DEFAULT_MODEL
    ):
        self._client = client
        self._model = model

    def _ensure_client(self) -> CompletionClient:
        if self._client is None:
            self._client = AnthropicClient()
        return self._client

    def complete(
        self,
        *,
        system: str,
        user: str,
        model: Optional[str] = None,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        client = self._ensure_client()
        return client.complete(
            system=system, user=user, model=model or self._model, max_tokens=max_tokens
        )
