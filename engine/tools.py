"""External tool — gate-checked web search (Tavily).

This is the reference doc's headline reliability case: external tools fail far more often
than the model (timeouts, rate limits, malformed payloads, schema drift). A gate sits
between the Action (the API call) and the Observation (what the chain consumes): the raw
response is validated against a Pydantic schema, transient failures trigger a controlled
retry, and after the cap we return a typed `ToolFailure` instead of letting a broken
observation corrupt the reasoning chain.

The HTTP call is hidden behind an injectable `transport`, so the whole thing is testable
offline with zero network calls and no API key.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from pydantic import BaseModel, ValidationError

from engine.errors import ToolFailure
from engine.trace import RunTrace

# A transport takes a query (plus max_results) and returns the raw, parsed JSON dict.
Transport = Callable[..., dict]


class RawSearchResult(BaseModel):
    title: str
    url: str
    content: str


class RawSearchResponse(BaseModel):
    results: list[RawSearchResult]


@dataclass
class Evidence:
    title: str
    url: str
    snippet: str


def _reason_from_validation(error: ValidationError) -> str:
    """Compact one-line reason (mirrors gates._summarise; kept local to decouple tools)."""
    parts = []
    for err in error.errors():
        loc = ".".join(str(x) for x in err.get("loc", ()))
        parts.append(f"{loc}: {err.get('msg')}" if loc else str(err.get("msg")))
    return "; ".join(parts) or str(error)


def tavily_transport(query: str, *, max_results: int = 3, timeout: float = 10.0) -> dict:
    """Real transport. Used only for live runs; tests inject a fake instead."""
    import os

    import httpx

    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY is not set. Add it to .env for live search runs.")
    resp = httpx.post(
        "https://api.tavily.com/search",
        json={
            "api_key": api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
        },
        timeout=timeout,
    )
    resp.raise_for_status()  # 429/5xx raise HTTPStatusError -> caught as a transient failure
    return resp.json()


def search_evidence(
    query: str,
    *,
    transport: Transport = tavily_transport,
    trace: Optional[RunTrace] = None,
    max_results: int = 3,
    max_attempts: int = 3,
    max_snippet_chars: int = 500,
) -> tuple[Optional[list[Evidence]], Optional[ToolFailure]]:
    """Search for evidence behind a validation gate. Returns (evidence, None) on success
    or (None, ToolFailure) after exhausting retries."""
    last_reason = ""

    for attempt in range(1, max_attempts + 1):
        # --- Action: call the external tool (may raise on timeout / rate limit / network) ---
        try:
            raw = transport(query, max_results=max_results)
        except Exception as e:  # transport-level transient failure
            last_reason = f"transport error: {type(e).__name__}: {e}"
            _record_failure(trace, attempt, max_attempts, last_reason)
            continue

        # --- Gate check: validate the raw observation against the schema ---
        try:
            parsed = RawSearchResponse.model_validate(raw)
        except ValidationError as e:
            last_reason = _reason_from_validation(e)
            _record_failure(trace, attempt, max_attempts, last_reason)
            continue

        evidence = [
            Evidence(title=r.title, url=r.url, snippet=r.content[:max_snippet_chars])
            for r in parsed.results
        ]
        if trace is not None:
            trace.record(
                step="search_evidence",
                attempt=attempt,
                outcome="ok",
                note=f"{len(evidence)} result(s)",
            )
        return evidence, None

    return None, ToolFailure(tool="tavily", reason=last_reason, attempts=max_attempts)


def _record_failure(
    trace: Optional[RunTrace], attempt: int, max_attempts: int, reason: str
) -> None:
    if trace is None:
        return
    trace.record(
        step="search_evidence",
        attempt=attempt,
        outcome="retry" if attempt < max_attempts else "tool_failed",
        retry_reason=reason,
    )
