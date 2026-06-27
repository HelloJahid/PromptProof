"""Gate checks — the reliability heart of the engine.

A gate sits between chain steps and validates an intermediate output against a Pydantic
schema *before* it flows downstream. `generate_and_validate` wraps an LLM call in that
gate and implements the three responses the reference doc describes:

  - halt   : after `max_attempts`, return a typed GateFailure instead of crashing
  - retry  : ask again
  - retry-with-feedback : ask again with the validation reason injected into the prompt

The mechanism is generic: pass a different `parse` callable to gate any step.
"""

from __future__ import annotations

import json
from typing import Callable, Literal, Optional, TypeVar

from pydantic import BaseModel, TypeAdapter, ValidationError, field_validator

from engine.errors import GateFailure
from engine.llm import LLM
from engine.trace import RunTrace

T = TypeVar("T")

VerdictLabel = Literal["Supported", "Refuted", "Unverifiable"]


class VerdictModel(BaseModel):
    """One judged claim. The `Literal` on `verdict` IS the gate: any other value
    (e.g. "Maybe", "True") is rejected automatically by Pydantic. `source` is the
    citation URL the evidence-grounded judge relied on (empty string for Unverifiable)."""

    claim: str
    verdict: VerdictLabel
    reason: str
    source: str  # required key; may be "" when Unverifiable

    @field_validator("claim", "reason")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be empty")
        return v


class GateError(Exception):
    """Raised by a `parse` callable when validation fails. `reason` is short and
    model-friendly so it can be fed straight back into a retry-with-feedback prompt."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


_CLAIMS_ADAPTER = TypeAdapter(list[str])
_VERDICTS_ADAPTER = TypeAdapter(list[VerdictModel])


def _summarise(error: ValidationError) -> str:
    """Turn a Pydantic ValidationError into a compact one-line reason."""
    parts = []
    for err in error.errors():
        loc = ".".join(str(x) for x in err.get("loc", ()))
        parts.append(f"{loc}: {err.get('msg')}" if loc else str(err.get("msg")))
    return "; ".join(parts) or str(error)


def _loads_json_array(text: str):
    """Best-effort JSON load tolerant of a stray ```json fence. Raises GateError if
    no JSON array can be recovered at all."""
    s = text.strip()
    if s.startswith("```"):
        s = s.strip("`")
        if "[" in s:
            s = s[s.find("[") :]
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        i, j = s.find("["), s.rfind("]")
        if i != -1 and j > i:
            try:
                return json.loads(s[i : j + 1])
            except json.JSONDecodeError as e:
                raise GateError(f"output was not valid JSON: {e}") from e
        raise GateError("output did not contain a JSON array")


def parse_claims(text: str) -> list[str]:
    """Gate for the extract step: a non-empty list of non-empty claim strings."""
    data = _loads_json_array(text)
    try:
        claims = _CLAIMS_ADAPTER.validate_python(data)
    except ValidationError as e:
        raise GateError(_summarise(e)) from e
    claims = [c.strip() for c in claims]
    if not claims or any(not c for c in claims):
        raise GateError("expected a non-empty list of non-empty claim strings")
    return claims


def parse_verdicts(text: str) -> list[VerdictModel]:
    """Gate for the judge step: a non-empty list of VerdictModel (enforces the enum)."""
    data = _loads_json_array(text)
    try:
        verdicts = _VERDICTS_ADAPTER.validate_python(data)
    except ValidationError as e:
        raise GateError(_summarise(e)) from e
    if not verdicts:
        raise GateError("expected a non-empty list of verdict objects")
    return verdicts


def generate_and_validate(
    *,
    llm: LLM,
    system: str,
    user: str,
    parse: Callable[[str], T],
    step_name: str,
    trace: Optional[RunTrace] = None,
    model: Optional[str] = None,
    max_tokens: int = 1024,
    max_attempts: int = 3,
) -> tuple[Optional[T], Optional[GateFailure]]:
    """Run the LLM behind a gate. Returns (value, None) on success or
    (None, GateFailure) after exhausting retries."""
    feedback = ""
    last_text = ""
    last_reason = ""

    for attempt in range(1, max_attempts + 1):
        full_user = user if not feedback else f"{user}\n\n{feedback}"
        resp = llm.complete(
            system=system, user=full_user, model=model, max_tokens=max_tokens
        )
        last_text = resp.text

        try:
            value = parse(resp.text)
        except GateError as e:
            last_reason = e.reason
            outcome = "retry" if attempt < max_attempts else "gate_failed"
            if trace is not None:
                trace.record(
                    step=step_name,
                    attempt=attempt,
                    outcome=outcome,
                    retry_reason=e.reason,
                    model=resp.model,
                    input_tokens=resp.input_tokens,
                    output_tokens=resp.output_tokens,
                )
            feedback = (
                f"Your previous response failed validation: {e.reason}. "
                "Return only valid JSON matching the required schema, and nothing else."
            )
            continue

        if trace is not None:
            trace.record(
                step=step_name,
                attempt=attempt,
                outcome="ok",
                model=resp.model,
                input_tokens=resp.input_tokens,
                output_tokens=resp.output_tokens,
            )
        return value, None

    return None, GateFailure(step=step_name, reason=last_reason, raw=last_text)
