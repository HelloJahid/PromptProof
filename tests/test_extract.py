"""Phase 1/3b tests — the (now gated) claim-extraction step, fully offline."""

import json

from engine.llm import LLM, MockClient
from engine.prompts.extract import build_extract_prompt
from engine.steps.extract import extract_claims
from engine.trace import RunTrace

PARA = "The Eiffel Tower is in Paris. It was completed in 1889 and is made of aluminium."


def test_prompt_carries_all_five_refinement_components():
    system, user = build_extract_prompt(PARA)
    blob = (system + user).lower()
    assert "fact-checking analyst" in blob          # ROLE
    assert "atomic claims" in blob                   # TASK
    assert "json array" in blob                      # FORMAT
    assert "sydney opera house" in blob              # EXAMPLES
    assert "one verifiable fact per claim" in blob   # CONTEXT
    assert PARA in user


def test_extract_parses_claims_and_records_an_ok_trace_step():
    scripted = json.dumps(
        [
            "The Eiffel Tower is in Paris.",
            "The Eiffel Tower was completed in 1889.",
            "The Eiffel Tower is made of aluminium.",
        ]
    )
    trace = RunTrace()
    result = extract_claims(PARA, LLM(client=MockClient(responses=[scripted])), trace=trace)

    assert result.ok
    assert len(result.claims) == 3
    assert result.claims[0] == "The Eiffel Tower is in Paris."
    assert trace.records[-1].step == "extract_claims"
    assert trace.records[-1].outcome == "ok"


def test_extract_tolerates_an_accidental_code_fence():
    scripted = '```json\n["a single claim"]\n```'
    result = extract_claims(PARA, LLM(client=MockClient(responses=[scripted])))
    assert result.ok
    assert result.claims == ["a single claim"]


def test_extract_halts_with_a_gate_failure_on_unrecoverable_output():
    # The gate retries, then halts with a structured failure (no silent []).
    llm = LLM(client=MockClient(responses=["Sure! Here are the claims you asked for."]))
    result = extract_claims(PARA, llm)
    assert not result.ok
    assert result.claims == []
    assert result.failure is not None
    assert result.failure.step == "extract_claims"
