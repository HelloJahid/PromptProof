"""Step 1 — extract atomic claims from a paragraph (now gated).

The naive parser is gone. The step runs behind `generate_and_validate`, so a malformed
extraction is retried with feedback and, if it never validates, returns a typed
GateFailure instead of silently degrading to [].
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from engine.errors import GateFailure
from engine.gates import generate_and_validate, parse_claims
from engine.llm import LLM
from engine.prompts.extract import build_extract_prompt
from engine.trace import RunTrace


@dataclass
class ExtractResult:
    claims: list[str]
    failure: Optional[GateFailure] = None

    @property
    def ok(self) -> bool:
        return self.failure is None


def extract_claims(
    paragraph: str,
    llm: LLM,
    *,
    trace: Optional[RunTrace] = None,
    model: Optional[str] = None,
    max_tokens: int = 800,
    max_attempts: int = 3,
) -> ExtractResult:
    system, user = build_extract_prompt(paragraph)
    claims, failure = generate_and_validate(
        llm=llm,
        system=system,
        user=user,
        parse=parse_claims,
        step_name="extract_claims",
        trace=trace,
        model=model,
        max_tokens=max_tokens,
        max_attempts=max_attempts,
    )
    return ExtractResult(claims=claims or [], failure=failure)
