"""Phase 4b/5b tests — the full extract -> search -> judge -> evaluate(-> revise) chain."""

import json

from engine.chain import run_chain
from engine.llm import LLM, MockClient

PARA = "The Eiffel Tower is in Paris. It is made of aluminium."
ONE_CLAIM = "The Eiffel Tower is in Paris."


class FakeTransport:
    """Returns one evidence result per query; records calls."""

    def __init__(self):
        self.calls = []

    def __call__(self, query, *, max_results=3):
        self.calls.append(query)
        return {
            "results": [
                {"title": "src", "url": f"https://ex.com/{len(self.calls)}", "content": query}
            ]
        }


def _verdict(claim, verdict, source):
    return {"claim": claim, "verdict": verdict, "reason": "because evidence.", "source": source}


def test_chain_runs_full_pipeline_and_grounds_the_judge_in_evidence():
    extract_out = json.dumps(
        ["The Eiffel Tower is in Paris.", "The Eiffel Tower is made of aluminium."]
    )
    judge_out = json.dumps(
        [
            _verdict("The Eiffel Tower is in Paris.", "Supported", "https://ex.com/1"),
            _verdict("The Eiffel Tower is made of aluminium.", "Refuted", "https://ex.com/2"),
        ]
    )
    client = MockClient(responses=[extract_out, judge_out])
    transport = FakeTransport()

    report = run_chain(PARA, LLM(client=client), transport=transport)

    assert report.ok
    assert report.evaluation is not None and report.evaluation.passed
    assert len(transport.calls) == 2
    assert "https://ex.com/1" in client.calls[1]["user"]  # evidence reached the judge
    assert [v.verdict for v in report.verdicts] == ["Supported", "Refuted"]
    steps = [r.step for r in report.trace.records]
    assert steps == [
        "extract_claims",
        "search_evidence",
        "search_evidence",
        "judge_claims",
        "evaluate_report",
    ]


def test_feedback_loop_revises_an_uncited_verdict_then_passes():
    extract_out = json.dumps([ONE_CLAIM])
    judge_bad = json.dumps([_verdict(ONE_CLAIM, "Supported", "")])     # Supported, no source
    judge_good = json.dumps([_verdict(ONE_CLAIM, "Supported", "https://ex.com/1")])
    client = MockClient(responses=[extract_out, judge_bad, judge_good])

    report = run_chain(PARA, LLM(client=client), transport=FakeTransport())

    assert report.evaluation.passed
    assert report.verdicts[0].source == "https://ex.com/1"
    # The second judge call carried the evaluator's revision feedback.
    assert "Revise" in client.calls[2]["user"]
    # Two evaluations happened: first "revise", then "ok".
    evals = [r for r in report.trace.records if r.step == "evaluate_report"]
    assert [e.outcome for e in evals] == ["revise", "ok"]


def test_feedback_loop_stops_at_the_iteration_cap():
    extract_out = json.dumps([ONE_CLAIM])
    judge_bad = json.dumps([_verdict(ONE_CLAIM, "Supported", "")])
    client = MockClient(responses=[extract_out, judge_bad, judge_bad])

    report = run_chain(PARA, LLM(client=client), transport=FakeTransport(), max_iterations=2)

    assert not report.evaluation.passed     # never satisfied, but it stopped
    assert len(client.calls) == 3           # extract + judge x2 (the cap), no third judge
    evals = [r for r in report.trace.records if r.step == "evaluate_report"]
    assert len(evals) == 2


def test_chain_halts_on_failed_extraction_without_searching_or_judging():
    client = MockClient(responses=["not a json array"])
    transport = FakeTransport()

    report = run_chain(PARA, LLM(client=client), transport=transport)

    assert not report.ok
    assert report.failure.step == "extract_claims"
    assert report.claims == [] and report.verdicts == []
    assert transport.calls == []
    assert not any(r.step == "search_evidence" for r in report.trace.records)
