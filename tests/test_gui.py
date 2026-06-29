"""Phase 9 tests — GUI rendering + the analyse() wrapper, fully offline.

Imports only `report_to_markdown` and `analyse` from app.gui, which do NOT import Streamlit
(it is lazy-imported inside main()), so these run without the GUI dependency installed.
"""

import json

from app.gui import analyse, report_to_markdown
from engine.chain import Report
from engine.errors import GateFailure
from engine.feedback import Evaluation
from engine.gates import VerdictModel
from engine.llm import LLM, MockClient
from engine.trace import RunTrace


def _report(verdicts, *, evaluation=None, failure=None):
    return Report(
        paragraph="p",
        claims=[v.claim for v in verdicts],
        verdicts=verdicts,
        trace=RunTrace(),
        failure=failure,
        evaluation=evaluation,
    )


class _FakeSearch:
    def __call__(self, query, *, max_results=3):
        return {"results": [{"title": "t", "url": "https://ex.com/1", "content": query}]}


def test_markdown_renders_badges_and_source_links():
    verdicts = [
        VerdictModel(claim="A", verdict="Supported", reason="r1", source="https://x"),
        VerdictModel(claim="B", verdict="Refuted", reason="r2", source="https://y"),
    ]
    md = report_to_markdown(_report(verdicts, evaluation=Evaluation(True, [])))
    assert "✅" in md and "Supported" in md
    assert "❌" in md and "Refuted" in md
    assert "[source](https://x)" in md
    assert "passed" in md


def test_markdown_unverifiable_has_no_source_link():
    verdicts = [VerdictModel(claim="A", verdict="Unverifiable", reason="no evidence", source="")]
    md = report_to_markdown(_report(verdicts, evaluation=Evaluation(True, [])))
    assert "❓" in md
    assert "source]" not in md


def test_markdown_halted_report_shows_the_failure():
    failure = GateFailure(step="extract_claims", reason="bad json")
    md = report_to_markdown(_report([], failure=failure))
    assert "halted" in md.lower()
    assert "extract_claims" in md


def test_analyse_runs_the_engine_with_injected_mocks():
    extract_out = json.dumps(["The Eiffel Tower is in Paris."])
    judge_out = json.dumps(
        [
            {
                "claim": "The Eiffel Tower is in Paris.",
                "verdict": "Supported",
                "reason": "evidence confirms it",
                "source": "https://ex.com/1",
            }
        ]
    )
    report = analyse(
        "para",
        llm=LLM(client=MockClient(responses=[extract_out, judge_out])),
        transport=_FakeSearch(),
    )
    assert report.ok
    assert report.verdicts[0].verdict == "Supported"
