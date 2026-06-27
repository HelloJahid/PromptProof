"""Phase 1 tests — the claim-extraction step, fully offline via MockClient."""

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
    assert PARA in user                              # the paragraph is injected


def test_extract_parses_claims_and_records_a_trace_step():
    scripted = json.dumps(
        [
            "The Eiffel Tower is in Paris.",
            "The Eiffel Tower was completed in 1889.",
            "The Eiffel Tower is made of aluminium.",
        ]
    )
    trace = RunTrace()
    llm = LLM(client=MockClient(responses=[scripted]))

    result = extract_claims(PARA, llm, trace=trace)

    assert len(result.claims) == 3
    assert result.claims[0] == "The Eiffel Tower is in Paris."
    assert trace.records[-1].step == "extract_claims"


def test_extract_tolerates_an_accidental_code_fence():
    scripted = '```json\n["a single claim"]\n```'
    llm = LLM(client=MockClient(responses=[scripted]))
    assert extract_claims(PARA, llm).claims == ["a single claim"]


def test_extract_is_fragile_without_a_gate():
    # No Pydantic gate yet (Phase 3): malformed output silently degrades to [].
    llm = LLM(client=MockClient(responses=["Sure! Here are the claims you asked for."]))
    assert extract_claims(PARA, llm).claims == []
