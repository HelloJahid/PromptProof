"""The prompt chain — orchestrates the steps in dependency order.

Phase 2: two links, extract -> judge. The output of step 1 (claims) becomes the input
of step 2 (verdicts). There are no gate checks between them yet, so a bad extraction
flows straight into the judge — the "domino effect" the reference doc warns about.
Phase 3 inserts the gates; Phase 4 inserts the web-search step between extract and judge.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from engine.llm import LLM
from engine.steps.extract import extract_claims
from engine.steps.judge import Verdict, judge_claims
from engine.trace import RunTrace


@dataclass
class Report:
    paragraph: str
    claims: list[str]
    verdicts: list[Verdict]
    trace: RunTrace = field(default_factory=RunTrace)


def run_chain(
    paragraph: str,
    llm: LLM,
    *,
    trace: Optional[RunTrace] = None,
    model: Optional[str] = None,
) -> Report:
    trace = trace if trace is not None else RunTrace()

    extracted = extract_claims(paragraph, llm, trace=trace, model=model)
    judged = judge_claims(extracted.claims, llm, trace=trace, model=model)

    return Report(
        paragraph=paragraph,
        claims=extracted.claims,
        verdicts=judged.verdicts,
        trace=trace,
    )
