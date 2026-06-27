"""Step 2 — judge each claim Supported / Refuted / Unverifiable (now gated).

Runs behind `generate_and_validate` with `parse_verdicts`, so the verdict enum and
object shape are enforced by the gate. Returns typed `VerdictModel`s (from gates) or a
GateFailure. Still grounded only in the model's own knowledge — Phase 4 adds evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from engine.errors import GateFailure
from engine.gates import VerdictModel, generate_and_validate, parse_verdicts
from engine.llm import LLM
from engine.prompts.judge import build_judge_prompt
from engine.trace import RunTrace


@dataclass
class JudgeResult:
    verdicts: list[VerdictModel]
    failure: Optional[GateFailure] = None

    @property
    def ok(self) -> bool:
        return self.failure is None


def judge_claims(
    claims: list[str],
    llm: LLM,
    *,
    trace: Optional[RunTrace] = None,
    model: Optional[str] = None,
    max_tokens: int = 1200,
    max_attempts: int = 3,
) -> JudgeResult:
    system, user = build_judge_prompt(claims)
    verdicts, failure = generate_and_validate(
        llm=llm,
        system=system,
        user=user,
        parse=parse_verdicts,
        step_name="judge_claims",
        trace=trace,
        model=model,
        max_tokens=max_tokens,
        max_attempts=max_attempts,
    )
    return JudgeResult(verdicts=verdicts or [], failure=failure)
