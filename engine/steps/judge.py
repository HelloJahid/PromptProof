"""Step 3 — judge each claim against its evidence (gated, evidence-grounded).

Takes claims paired with the evidence retrieved by the search tool, serialises them for
the prompt, and runs behind `generate_and_validate` with `parse_verdicts`. Returns typed
`VerdictModel`s (with a `source` citation) or a GateFailure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from engine.errors import GateFailure
from engine.gates import VerdictModel, generate_and_validate, parse_verdicts
from engine.llm import LLM
from engine.prompts.judge import build_judge_prompt
from engine.tools import Evidence
from engine.trace import RunTrace


@dataclass
class ClaimEvidence:
    claim: str
    evidence: list[Evidence] = field(default_factory=list)


@dataclass
class JudgeResult:
    verdicts: list[VerdictModel]
    failure: Optional[GateFailure] = None

    @property
    def ok(self) -> bool:
        return self.failure is None


def _to_payload(items: list[ClaimEvidence]) -> list[dict]:
    return [
        {
            "claim": it.claim,
            "evidence": [
                {"title": e.title, "url": e.url, "snippet": e.snippet} for e in it.evidence
            ],
        }
        for it in items
    ]


def judge_claims(
    items: list[ClaimEvidence],
    llm: LLM,
    *,
    trace: Optional[RunTrace] = None,
    model: Optional[str] = None,
    feedback: Optional[str] = None,
    max_tokens: int = 1500,
    max_attempts: int = 3,
) -> JudgeResult:
    system, user = build_judge_prompt(_to_payload(items))
    if feedback:  # report-level revision feedback from the evaluator (Phase 5b)
        user = f"{user}\n\n{feedback}"
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
