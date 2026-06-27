"""Phase 4b tests — the full extract -> search -> judge chain, offline."""

import json

from engine.chain import run_chain
from engine.llm import LLM, MockClient

PARA = "The Eiffel Tower is in Paris. It is made of aluminium."


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


def test_chain_runs_extract_search_judge_and_grounds_the_judge_in_evidence():
    extract_out = json.dumps(
        ["The Eiffel Tower is in Paris.", "The Eiffel Tower is made of aluminium."]
    )
    judge_out = json.dumps(
        [
            {
                "claim": "The Eiffel Tower is in Paris.",
                "verdict": "Supported",
                "reason": "Evidence confirms Paris.",
                "source": "https://ex.com/1",
            },
            {
                "claim": "The Eiffel Tower is made of aluminium.",
                "verdict": "Refuted",
                "reason": "Evidence says iron.",
                "source": "https://ex.com/2",
            },
        ]
    )
    client = MockClient(responses=[extract_out, judge_out])
    transport = FakeTransport()

    report = run_chain(PARA, LLM(client=client), transport=transport)

    assert report.ok
    # The search tool was called once per claim...
    assert len(transport.calls) == 2
    # ...and the retrieved evidence (its url) reached the judge's prompt.
    assert "https://ex.com/1" in client.calls[1]["user"]
    assert [v.verdict for v in report.verdicts] == ["Supported", "Refuted"]
    assert report.verdicts[0].source == "https://ex.com/1"
    # Trace shows the full ReAct shape: extract, a search per claim, then judge.
    steps = [r.step for r in report.trace.records]
    assert steps == ["extract_claims", "search_evidence", "search_evidence", "judge_claims"]


def test_chain_halts_on_failed_extraction_without_searching_or_judging():
    client = MockClient(responses=["not a json array"])
    transport = FakeTransport()

    report = run_chain(PARA, LLM(client=client), transport=transport)

    assert not report.ok
    assert report.failure.step == "extract_claims"
    assert report.claims == [] and report.verdicts == []
    assert transport.calls == []  # search never ran
    assert not any(r.step == "search_evidence" for r in report.trace.records)
