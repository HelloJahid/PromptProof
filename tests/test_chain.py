"""Phase 2/3b tests — the extract -> judge chain, now gated, offline."""

import json

from engine.chain import run_chain
from engine.llm import LLM, MockClient

PARA = "The Eiffel Tower is in Paris. It is made of aluminium."


def test_chain_runs_extract_then_judge_and_passes_claims_downstream():
    extract_out = json.dumps(
        ["The Eiffel Tower is in Paris.", "The Eiffel Tower is made of aluminium."]
    )
    judge_out = json.dumps(
        [
            {
                "claim": "The Eiffel Tower is in Paris.",
                "verdict": "Supported",
                "reason": "Landmark.",
            },
            {
                "claim": "The Eiffel Tower is made of aluminium.",
                "verdict": "Refuted",
                "reason": "Iron.",
            },
        ]
    )
    client = MockClient(responses=[extract_out, judge_out])
    report = run_chain(PARA, LLM(client=client))

    assert report.ok
    # Step 1 output became step 2 input — the second call's prompt carries the claims.
    assert "The Eiffel Tower is in Paris." in client.calls[1]["user"]
    assert report.claims == [
        "The Eiffel Tower is in Paris.",
        "The Eiffel Tower is made of aluminium.",
    ]
    assert [v.verdict for v in report.verdicts] == ["Supported", "Refuted"]
    assert [r.step for r in report.trace.records] == ["extract_claims", "judge_claims"]


def test_chain_halts_on_failed_extraction_without_running_the_judge():
    # A broken extraction now halts cleanly: the judge is never called, and the
    # report carries the structured GateFailure instead of a poisoned result.
    client = MockClient(responses=["not a json array"])
    report = run_chain(PARA, LLM(client=client))

    assert not report.ok
    assert report.failure is not None
    assert report.failure.step == "extract_claims"
    assert report.claims == []
    assert report.verdicts == []
    # Only extract steps ran — no judge step in the trace.
    assert all(r.step == "extract_claims" for r in report.trace.records)
    assert not any(r.step == "judge_claims" for r in report.trace.records)
