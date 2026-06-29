"""The prompt chain — orchestrates the steps in dependency order.

  1. extract atomic claims            (gated; halts on failure)
  2. search evidence per claim        (gate-checked tool call, run concurrently)
  3. judge each claim vs its evidence (gated, evidence-grounded, cited)
  4. evaluate the report; if it fails the criteria, re-judge with the issues as feedback,
     looping until it passes or hits `max_iterations`

The per-claim searches are independent, so they run concurrently (their latency is the
slowest single search, not the sum). An optional `progress` callback emits human-readable
stage messages for a UI; the timed `RunTrace` records seconds per step for diagnosis.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable, Optional

from engine.errors import GateFailure
from engine.feedback import Evaluation, evaluate_report, issues_as_feedback
from engine.gates import VerdictModel
from engine.llm import LLM
from engine.steps.extract import extract_claims
from engine.steps.judge import ClaimEvidence, judge_claims
from engine.tools import Transport, search_evidence, tavily_transport
from engine.trace import RunTrace

ProgressFn = Callable[[str], None]


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


def _emit(progress: Optional[ProgressFn], message: str) -> None:
    if progress is not None:
        progress(message)


def _gather_evidence(
    claims: list[str],
    *,
    transport: Transport,
    trace: RunTrace,
    max_results: int,
) -> list[ClaimEvidence]:
    """Search for every claim concurrently. Order of `items` follows `claims`."""
    items = [ClaimEvidence(claim=c) for c in claims]
    if not claims:
        return items
    with ThreadPoolExecutor(max_workers=min(len(claims), 5)) as pool:
        futures = {
            pool.submit(
                search_evidence, claim, transport=transport, trace=trace, max_results=max_results
            ): i
            for i, claim in enumerate(claims)
        }
        for future in as_completed(futures):
            i = futures[future]
            evidence, _tool_failure = future.result()
            items[i].evidence = evidence or []
    return items


def run_chain(
    paragraph: str,
    llm: LLM,
    *,
    transport: Transport = tavily_transport,
    trace: Optional[RunTrace] = None,
    model: Optional[str] = None,
    max_results: int = 3,
    max_iterations: int = 2,
    progress: Optional[ProgressFn] = None,
) -> Report:
    trace = trace if trace is not None else RunTrace()

    # Step 1 — extract (halt on gate failure).
    _emit(progress, "Extracting claims…")
    extracted = extract_claims(paragraph, llm, trace=trace, model=model)
    if extracted.failure is not None:
        return Report(
            paragraph=paragraph, claims=[], verdicts=[], trace=trace, failure=extracted.failure
        )

    # Step 2 — retrieve evidence per claim (concurrently).
    _emit(progress, f"Searching evidence for {len(extracted.claims)} claim(s)…")
    items = _gather_evidence(
        extracted.claims, transport=transport, trace=trace, max_results=max_results
    )

    # Steps 3 + 4 — judge, then evaluate-and-revise until it passes or the cap is hit.
    _emit(progress, f"Judging {len(items)} claim(s) against the evidence…")
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
            return report

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
        _emit(progress, f"Revising the report (iteration {iteration})…")
        judged = judge_claims(
            items,
            llm,
            trace=trace,
            model=model,
            feedback=issues_as_feedback(evaluation.issues),
        )
