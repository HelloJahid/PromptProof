"""Phase 5a tests — the rule-based evaluator, fully offline."""

from engine.chain import Report
from engine.errors import GateFailure
from engine.feedback import evaluate_report, issues_as_feedback
from engine.gates import VerdictModel


def _verdict(claim, verdict, reason="ok", source="https://ex.com"):
    return VerdictModel(claim=claim, verdict=verdict, reason=reason, source=source)


def _report(claims, verdicts, failure=None):
    return Report(paragraph="p", claims=claims, verdicts=verdicts, failure=failure)


def test_clean_report_passes():
    claims = ["a", "b"]
    verdicts = [_verdict("a", "Supported"), _verdict("b", "Unverifiable", source="")]
    result = evaluate_report(_report(claims, verdicts))
    assert result.passed
    assert result.issues == []


def test_coverage_mismatch_is_flagged():
    result = evaluate_report(_report(["a", "b"], [_verdict("a", "Supported")]))
    assert not result.passed
    assert any("coverage mismatch" in i for i in result.issues)


def test_supported_without_a_source_is_flagged():
    verdicts = [_verdict("a", "Supported", source="")]
    result = evaluate_report(_report(["a"], verdicts))
    assert not result.passed
    assert any("cites no source" in i for i in result.issues)


def test_unverifiable_without_a_source_is_fine():
    verdicts = [_verdict("a", "Unverifiable", source="")]
    assert evaluate_report(_report(["a"], verdicts)).passed


def test_failed_chain_never_passes():
    failure = GateFailure(step="extract_claims", reason="bad json")
    result = evaluate_report(_report([], [], failure=failure))
    assert not result.passed
    assert any("did not complete" in i for i in result.issues)


def test_issues_as_feedback_lists_each_issue():
    text = issues_as_feedback(["coverage mismatch", "verdict 0 cites no source"])
    assert "- coverage mismatch" in text
    assert "- verdict 0 cites no source" in text
    assert "Revise" in text
