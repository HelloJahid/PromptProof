"""The prompt chain — orchestrates the steps in dependency order.

Phase 5b: the full engine, including the feedback loop.

  1. extract atomic claims            (gated; halts on failure)
  2. search evidence per claim        (gate-checked tool call)
  3. judge each claim vs its evidence (gated, evidence-grounded, cited)
  4. evaluate the report; if it fails the criteria, re-judge with the issues as feedback,
     looping until it passes or hits `max_iterations`

Only the cheap judge step re-runs in the loop (evidence is already retrieved), and the loop
is bounded, so the engine always terminates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from engine.errors import GateFailure
from engine.feedback import Evaluation, evaluate_report, issues_as_feedback
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
    evaluation: Optional[Evaluation] = None

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
    max_iterations: int = 2,
) -> Report:
    trace = trace if trace is not None else RunTrace()

    # Step 1 — extract (halt on gate failure).
    extracted = extract_claims(paragraph, llm, trace=trace, model=model)
    if extracted.failure is not None:
        return Report(
            paragraph=paragraph, claims=[], verdicts=[], trace=trace, failure=extracted.failure
        )

    # Step 2 — retrieve evidence per claim.
    items: list[ClaimEvidence] = []
    for claim in extracted.claims:
        evidence, _tool_failure = search_evidence(
            claim, transport=transport, trace=trace, max_results=max_results
        )
        items.append(ClaimEvidence(claim=claim, evidence=evidence or []))

    # Steps 3 + 4 — judge, then evaluate-and-revise until it passes or the cap is hit.
    judged = judge_claims(items, llm, trace=trace, model=model)
    iteration = 1
    while True:
        report = Report(
            paragraph=paragraph,
            claims=extracted.claims,
            verdicts=judged.verdicts,
            evidence=items,
            trace=trace,
            failure=judged.failure,
        )
        if judged.failure is not None:
            return report  # a judge gate failure halts the loop

        evaluation = evaluate_report(report)
        report.evaluation = evaluation
        trace.record(
            step="evaluate_report",
            attempt=iteration,
            outcome="ok" if evaluation.passed else "revise",
            retry_reason=None if evaluation.passed else "; ".join(evaluation.issues),
        )
        if evaluation.passed or iteration >= max_iterations:
            return report

        iteration += 1
        judged = judge_claims(
            items,
            llm,
            trace=trace,
            model=model,
            feedback=issues_as_feedback(evaluation.issues),
        )
