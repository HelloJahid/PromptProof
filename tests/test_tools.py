"""Phase 4a tests — the gate-checked search tool, fully offline (no network, no key)."""

from engine.tools import Evidence, search_evidence
from engine.trace import RunTrace

VALID = {
    "results": [
        {"title": "Eiffel Tower", "url": "https://example.com/eiffel", "content": "It is in Paris."}
    ]
}


class FakeTransport:
    """Scripts transport outcomes: a dict is returned, an Exception is raised."""

    def __init__(self, behaviours):
        self._behaviours = list(behaviours)
        self.calls = []

    def __call__(self, query, *, max_results=3):
        self.calls.append({"query": query, "max_results": max_results})
        b = self._behaviours.pop(0) if self._behaviours else {}
        if isinstance(b, Exception):
            raise b
        return b


def test_search_returns_validated_evidence():
    transport = FakeTransport([VALID])
    evidence, failure = search_evidence("eiffel tower location", transport=transport)
    assert failure is None
    assert isinstance(evidence[0], Evidence)
    assert evidence[0].title == "Eiffel Tower"
    assert evidence[0].snippet == "It is in Paris."
    assert transport.calls[0]["max_results"] == 3  # default passed through


def test_search_retries_on_a_transient_error_then_succeeds():
    transport = FakeTransport([TimeoutError("read timed out"), VALID])
    trace = RunTrace()
    evidence, failure = search_evidence("q", transport=transport, trace=trace)
    assert failure is None
    assert len(evidence) == 1
    assert trace.records[0].outcome == "retry"
    assert "transport error" in trace.records[0].retry_reason


def test_search_gate_rejects_malformed_payload_then_halts():
    malformed = {"results": [{"title": "missing url and content"}]}
    transport = FakeTransport([malformed, malformed, malformed])
    trace = RunTrace()
    evidence, failure = search_evidence("q", transport=transport, max_attempts=3, trace=trace)
    assert evidence is None
    assert failure is not None
    assert failure.tool == "tavily"
    assert failure.attempts == 3
    assert len([r for r in trace.records if r.step == "search_evidence"]) == 3


def test_search_truncates_long_snippets():
    long = {"results": [{"title": "t", "url": "u", "content": "x" * 1000}]}
    evidence, _ = search_evidence(
        "q", transport=FakeTransport([long]), max_snippet_chars=100
    )
    assert len(evidence[0].snippet) == 100
