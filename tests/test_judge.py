"""Phase 2 tests — the judge step, fully offline via MockClient."""

import json

from engine.llm import LLM, MockClient
from engine.prompts.judge import build_judge_prompt
from engine.steps.judge import judge_claims
from engine.trace import RunTrace

CLAIMS = [
    "The Eiffel Tower is in Paris.",
    "The Eiffel Tower is made of aluminium.",
]


def test_judge_prompt_carries_the_five_components_and_verdict_enum():
    system, user = build_judge_prompt(CLAIMS)
    blob = (system + user).lower()
    assert "adjudicator" in blob                     # ROLE
    assert "classify each one" in blob               # TASK
    assert "json array of objects" in blob           # FORMAT
    assert "eiffel tower is in paris" in blob         # EXAMPLES
    assert "judge using only your own knowledge" in blob  # CONTEXT
    for v in ("supported", "refuted", "unverifiable"):    # verdict enum
        assert v in blob
    assert "The Eiffel Tower is made of aluminium." in user  # claims injected


def test_judge_parses_verdicts_and_records_a_trace_step():
    scripted = json.dumps(
        [
            {"claim": CLAIMS[0], "verdict": "Supported", "reason": "Well-known landmark."},
            {"claim": CLAIMS[1], "verdict": "Refuted", "reason": "It is wrought iron."},
        ]
    )
    trace = RunTrace()
    llm = LLM(client=MockClient(responses=[scripted]))

    result = judge_claims(CLAIMS, llm, trace=trace)

    assert [v.verdict for v in result.verdicts] == ["Supported", "Refuted"]
    assert result.verdicts[0].claim == CLAIMS[0]
    assert trace.records[-1].step == "judge_claims"


def test_judge_is_fragile_without_a_gate():
    # No gate yet: malformed output (and bad verdict values) degrade silently.
    llm = LLM(client=MockClient(responses=["I think the first one is true."]))
    assert judge_claims(CLAIMS, llm).verdicts == []
