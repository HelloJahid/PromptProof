"""Phase 7 tests — CLI rendering and arg parsing, fully offline (no live calls).

The `main()` glue builds real clients and hits the network by design, so we don't unit-test
it; instead we test the pure `format_report` and the parser, which carry all the logic.
"""

from app.cli import build_parser, format_report
from engine.chain import Report
from engine.errors import GateFailure
from engine.feedback import Evaluation
from engine.gates import VerdictModel
from engine.trace import RunTrace


def _report(verdicts, *, evaluation=None, failure=None, trace=None):
    return Report(
        paragraph="p",
        claims=[v.claim for v in verdicts],
        verdicts=verdicts,
        trace=trace or RunTrace(),
        failure=failure,
        evaluation=evaluation,
    )


def test_build_parser_reads_paragraph_and_flags():
    args = build_parser().parse_args(["some text", "--trace", "--max-iterations", "3"])
    assert args.paragraph == "some text"
    assert args.trace is True
    assert args.max_iterations == 3


def test_format_passing_report_shows_verdicts_and_sources():
    verdicts = [
        VerdictModel(claim="A is true", verdict="Supported", reason="evidence", source="https://x"),
        VerdictModel(claim="B is false", verdict="Refuted", reason="evidence", source="https://y"),
    ]
    out = format_report(_report(verdicts, evaluation=Evaluation(True, [])))
    assert "[Supported] A is true" in out
    assert "source: https://x" in out
    assert "Evaluation: PASSED" in out


def test_format_incomplete_report_lists_issues():
    verdicts = [VerdictModel(claim="A", verdict="Supported", reason="r", source="")]
    evaluation = Evaluation(False, ["verdict 0 ('A') is Supported but cites no source"])
    out = format_report(_report(verdicts, evaluation=evaluation))
    assert "Evaluation: INCOMPLETE" in out
    assert "cites no source" in out


def test_format_halted_report_shows_the_failure():
    failure = GateFailure(step="extract_claims", reason="output was not valid JSON")
    out = format_report(_report([], failure=failure))
    assert "RUN HALTED" in out
    assert "extract_claims" in out


def test_format_with_trace_appends_the_trace():
    trace = RunTrace()
    trace.record(step="extract_claims", outcome="ok", input_tokens=5, output_tokens=3)
    verdicts = [VerdictModel(claim="A", verdict="Supported", reason="r", source="https://x")]
    report = _report(verdicts, evaluation=Evaluation(True, []), trace=trace)
    out = format_report(report, show_trace=True)
    assert "--- trace ---" in out
    assert "extract_claims" in out
