"""Feedback loop — the evaluator (step 4 of the doc's progression).

`evaluate_report` reviews a finished report against explicit, external criteria and returns
a structured pass/fail with specific issues. It is **rule-based** on purpose: the current
best practice is evaluation-driven iteration against objective criteria, not "ask the model
to fix itself" (which can reinforce its own biases). Deterministic rules are also free and
perfectly testable.

Phase 5b feeds the returned `issues` back into the judge to drive revision until the report
passes or a max-iteration cap is hit. `issues_as_feedback` formats them for that prompt.

Typing note: we import `Report` only under TYPE_CHECKING to avoid a circular import with
`engine.chain` (which will import this module in 5b).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.chain import Report


@dataclass
class Evaluation:
    passed: bool
    issues: list[str]


def evaluate_report(report: "Report") -> Evaluation:
    """Check a report against the engine's quality criteria."""
    issues: list[str] = []

    # A chain that halted on a gate/tool failure cannot be a valid report.
    if report.failure is not None:
        f = report.failure
        issues.append(f"chain did not complete: {f.kind} at {f.step} ({f.reason})")
        return Evaluation(passed=False, issues=issues)

    if not report.claims:
        issues.append("no claims were extracted from the paragraph")

    # Coverage: every claim must have exactly one verdict.
    if len(report.verdicts) != len(report.claims):
        issues.append(
            f"coverage mismatch: {len(report.verdicts)} verdicts for "
            f"{len(report.claims)} claims"
        )

    # The per-item gate already guarantees non-empty claim/reason and a valid verdict
    # enum; the evaluator covers what a single-item gate cannot see — whole-report
    # coverage (above) and citation quality (below).
    for i, v in enumerate(report.verdicts):
        if v.verdict in ("Supported", "Refuted") and not v.source.strip():
            issues.append(f"verdict {i} ('{v.claim[:40]}') is {v.verdict} but cites no source")

    return Evaluation(passed=not issues, issues=issues)


def issues_as_feedback(issues: list[str]) -> str:
    """Render evaluator issues as a feedback block for a revision prompt (used in 5b)."""
    bullets = "\n".join(f"- {issue}" for issue in issues)
    return (
        "Your previous report had these problems:\n"
        f"{bullets}\n"
        "Revise so that every claim has exactly one verdict, and every Supported or "
        "Refuted verdict cites the url of the evidence it relied on."
    )
