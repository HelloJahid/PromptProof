"""The prompt chain — orchestrates the steps in dependency order.

Phase 3b: the gates now make the chain reliable. If the extract step fails its gate,
`run_chain` **halts** — it records the GateFailure and does not run the judge on a broken
extraction (no more domino effect). Phase 4 inserts the web-search step between extract
and judge.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from engine.errors import GateFailure
from engine.gates import VerdictModel
from engine.llm import LLM
from engine.steps.extract import extract_claims
from engine.steps.judge import judge_claims
from engine.trace import RunTrace


@dataclass
class Report:
    paragraph: str
    claims: list[str]
    verdicts: list[VerdictModel]
    trace: RunTrace = field(default_factory=RunTrace)
    failure: Optional[GateFailure] = None

    @property
    def ok(self) -> bool:
        return self.failure is None


def run_chain(
    paragraph: str,
    llm: LLM,
    *,
    trace: Optional[RunTrace] = None,
    model: Optional[str] = None,
) -> Report:
    trace = trace if trace is not None else RunTrace()

    extracted = extract_claims(paragraph, llm, trace=trace, model=model)
    if extracted.failure is not None:
        # Halt: a broken extraction must not flow into the judge.
        return Report(
            paragraph=paragraph,
            claims=[],
            verdicts=[],
            trace=trace,
            failure=extracted.failure,
        )

    judged = judge_claims(extracted.claims, llm, trace=trace, model=model)
    return Report(
        paragraph=paragraph,
        claims=extracted.claims,
        verdicts=judged.verdicts,
        trace=trace,
        failure=judged.failure,
    )
