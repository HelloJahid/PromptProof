"""The prompt chain — orchestrates the steps in dependency order.

Phase 4b: the full ReAct shape. extract -> (search evidence per claim) -> judge.

  1. extract atomic claims (gated; halts the run on failure)
  2. for each claim, retrieve evidence via the gate-checked search tool
  3. judge each claim against ITS evidence (gated, evidence-grounded, cited)

A per-claim search failure does not crash the run — that claim just gets no evidence,
which steers the judge to "Unverifiable". The judge's own gate failure still surfaces on
the Report. Phase 5 adds the evaluator feedback loop on top of this.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from engine.errors import GateFailure
from engine.gates import VerdictModel
from engine.llm import LLM
from engine.steps.extract import extract_claims
from engine.steps.judge import ClaimEvidence, judge_claims
from engine.tools import Transport, search_evidence, tavily_transport
from engine.trace import RunTrace


@dataclass
class Report:
    paragraph: str
    claims: list[str]
    verdicts: list[VerdictModel]
    evidence: list[ClaimEvidence] = field(default_factory=list)
    trace: RunTrace = field(default_factory=RunTrace)
    failure: Optional[GateFailure] = None

    @property
    def ok(self) -> bool:
        return self.failure is None


def run_chain(
    paragraph: str,
    llm: LLM,
    *,
    transport: Transport = tavily_transport,
    trace: Optional[RunTrace] = None,
    model: Optional[str] = None,
    max_results: int = 3,
) -> Report:
    trace = trace if trace is not None else RunTrace()

    # Step 1 — extract (halt on gate failure).
    extracted = extract_claims(paragraph, llm, trace=trace, model=model)
    if extracted.failure is not None:
        return Report(
            paragraph=paragraph, claims=[], verdicts=[], trace=trace, failure=extracted.failure
        )

    # Step 2 — retrieve evidence per claim (a tool failure leaves that claim evidence-less).
    items: list[ClaimEvidence] = []
    for claim in extracted.claims:
        evidence, _tool_failure = search_evidence(
            claim, transport=transport, trace=trace, max_results=max_results
        )
        items.append(ClaimEvidence(claim=claim, evidence=evidence or []))

    # Step 3 — judge each claim against its evidence.
    judged = judge_claims(items, llm, trace=trace, model=model)

    return Report(
        paragraph=paragraph,
        claims=extracted.claims,
        verdicts=judged.verdicts,
        evidence=items,
        trace=trace,
        failure=judged.failure,
    )
