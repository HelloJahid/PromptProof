"""Phase 4b tests — the evidence-grounded judge step, fully offline."""

import json

from engine.gates import VerdictModel
from engine.llm import LLM, MockClient
from engine.prompts.judge import build_judge_prompt
from engine.steps.judge import ClaimEvidence, judge_claims
from engine.tools import Evidence
from engine.trace import RunTrace

ITEMS = [
    ClaimEvidence(
        claim="The Eiffel Tower is in Paris.",
        evidence=[Evidence(title="Wiki", url="https://ex.com/eiffel", snippet="It is in Paris.")],
    ),
    ClaimEvidence(claim="The Eiffel Tower is made of aluminium.", evidence=[]),
]


def test_judge_prompt_is_evidence_grounded_and_carries_components():
    system, user = build_judge_prompt(
        [
            {
                "claim": "The Eiffel Tower is in Paris.",
                "evidence": [
                    {"title": "Wiki", "url": "https://ex.com/eiffel", "snippet": "Paris."}
                ],
            }
        ]
    )
    blob = (system + user).lower()
    assert "adjudicator" in blob                              # ROLE
    assert "classify each claim" in blob                      # TASK
    assert "json array of objects" in blob                    # FORMAT
    assert "eiffel tower is in paris" in blob                  # EXAMPLES
    assert "judge using only the supplied evidence" in blob   # CONTEXT (grounding)
    assert "source" in blob                                    # citation slot
    assert "https://ex.com/eiffel" in user                     # evidence is injected


def test_judge_returns_typed_cited_verdicts():
    scripted = json.dumps(
        [
            {
                "claim": "The Eiffel Tower is in Paris.",
                "verdict": "Supported",
                "reason": "Evidence says Paris.",
                "source": "https://ex.com/eiffel",
            },
            {
                "claim": "The Eiffel Tower is made of aluminium.",
                "verdict": "Unverifiable",
                "reason": "No evidence supplied.",
                "source": "",
            },
        ]
    )
    trace = RunTrace()
    result = judge_claims(ITEMS, LLM(client=MockClient(responses=[scripted])), trace=trace)

    assert result.ok
    assert all(isinstance(v, VerdictModel) for v in result.verdicts)
    assert [v.verdict for v in result.verdicts] == ["Supported", "Unverifiable"]
    assert result.verdicts[0].source == "https://ex.com/eiffel"
    assert trace.records[-1].step == "judge_claims"


def test_judge_halts_with_a_gate_failure_on_unrecoverable_output():
    result = judge_claims(ITEMS, LLM(client=MockClient(responses=["not json"])))
    assert not result.ok
    assert result.verdicts == []
    assert result.failure.step == "judge_claims"
