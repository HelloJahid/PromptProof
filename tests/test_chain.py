"""Phase 2 tests — the extract -> judge chain wired end to end, offline."""

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
    llm = LLM(client=client)

    report = run_chain(PARA, llm)

    # Step 1 output became step 2 input — the second call's prompt carries the claims.
    assert "The Eiffel Tower is in Paris." in client.calls[1]["user"]
    assert report.claims == [
        "The Eiffel Tower is in Paris.",
        "The Eiffel Tower is made of aluminium.",
    ]
    assert [v.verdict for v in report.verdicts] == ["Supported", "Refuted"]
    # Both steps are recorded in one trace.
    assert [r.step for r in report.trace.records] == ["extract_claims", "judge_claims"]


def test_chain_domino_effect_bad_extraction_yields_no_verdicts():
    # No gates yet: a broken extraction (empty claims) propagates — the judge has
    # nothing to rule on. This fragility is what Phase 3's gate checks will stop.
    client = MockClient(responses=["not json at all", "[]"])
    report = run_chain(PARA, LLM(client=client))
    assert report.claims == []
    assert report.verdicts == []
