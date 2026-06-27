"""Phase 2/3b tests — the (now gated) judge step, fully offline."""

import json

from engine.gates import VerdictModel
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
    assert "adjudicator" in blob                          # ROLE
    assert "classify each one" in blob                    # TASK
    assert "json array of objects" in blob                # FORMAT
    assert "eiffel tower is in paris" in blob              # EXAMPLES
    assert "judge using only your own knowledge" in blob  # CONTEXT
    for v in ("supported", "refuted", "unverifiable"):    # verdict enum
        assert v in blob
    assert "The Eiffel Tower is made of aluminium." in user


def test_judge_parses_typed_verdicts_and_records_an_ok_trace_step():
    scripted = json.dumps(
        [
            {"claim": CLAIMS[0], "verdict": "Supported", "reason": "Well-known landmark."},
            {"claim": CLAIMS[1], "verdict": "Refuted", "reason": "It is wrought iron."},
        ]
    )
    trace = RunTrace()
    result = judge_claims(CLAIMS, LLM(client=MockClient(responses=[scripted])), trace=trace)

    assert result.ok
    assert all(isinstance(v, VerdictModel) for v in result.verdicts)
    assert [v.verdict for v in result.verdicts] == ["Supported", "Refuted"]
    assert result.verdicts[0].claim == CLAIMS[0]
    assert trace.records[-1].step == "judge_claims"
    assert trace.records[-1].outcome == "ok"


def test_judge_halts_with_a_gate_failure_on_unrecoverable_output():
    llm = LLM(client=MockClient(responses=["I think the first one is true."]))
    result = judge_claims(CLAIMS, llm)
    assert not result.ok
    assert result.verdicts == []
    assert result.failure is not None
    assert result.failure.step == "judge_claims"
