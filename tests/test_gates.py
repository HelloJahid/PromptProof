"""Phase 3a tests — the gate machinery in isolation, fully offline."""

import json

import pytest

from engine.gates import (
    GateError,
    VerdictModel,
    generate_and_validate,
    parse_claims,
    parse_verdicts,
)
from engine.llm import LLM, MockClient
from engine.trace import RunTrace

# --- the parsers (schemas as gates) ---------------------------------------------------

def test_parse_claims_accepts_a_valid_list():
    assert parse_claims('["alpha", "beta"]') == ["alpha", "beta"]


def test_parse_claims_rejects_a_non_list():
    with pytest.raises(GateError):
        parse_claims('{"claim": "x"}')


def test_parse_claims_rejects_non_json():
    with pytest.raises(GateError):
        parse_claims("here are your claims")


def test_parse_verdicts_accepts_valid_objects():
    good = json.dumps([{"claim": "c", "verdict": "Supported", "reason": "r"}])
    out = parse_verdicts(good)
    assert isinstance(out[0], VerdictModel)
    assert out[0].verdict == "Supported"


def test_verdict_enum_gate_rejects_a_bad_label():
    bad = json.dumps([{"claim": "c", "verdict": "Maybe", "reason": "r"}])
    with pytest.raises(GateError) as ei:
        parse_verdicts(bad)
    assert "verdict" in str(ei.value).lower()


# --- the retry/halt loop --------------------------------------------------------------

def test_generate_and_validate_passes_on_first_try():
    trace = RunTrace()
    value, failure = generate_and_validate(
        llm=LLM(client=MockClient(responses=['["a", "b"]'])),
        system="s",
        user="u",
        parse=parse_claims,
        step_name="extract_claims",
        trace=trace,
    )
    assert value == ["a", "b"]
    assert failure is None
    assert trace.records[-1].outcome == "ok"
    assert trace.records[-1].attempt == 1


def test_retry_with_feedback_recovers_on_second_attempt():
    client = MockClient(responses=["not json", '["a"]'])
    trace = RunTrace()
    value, failure = generate_and_validate(
        llm=LLM(client=client),
        system="s",
        user="u",
        parse=parse_claims,
        step_name="extract_claims",
        trace=trace,
    )
    assert value == ["a"]
    assert failure is None
    # Attempt 1 recorded as a retry with a reason; attempt 2's prompt carries the feedback.
    assert trace.records[0].outcome == "retry"
    assert trace.records[0].retry_reason
    assert "failed validation" in client.calls[1]["user"]


def test_halts_with_a_gate_failure_after_the_cap():
    client = MockClient(responses=["bad", "still bad", "nope"])
    trace = RunTrace()
    value, failure = generate_and_validate(
        llm=LLM(client=client),
        system="s",
        user="u",
        parse=parse_claims,
        step_name="extract_claims",
        trace=trace,
        max_attempts=3,
    )
    assert value is None
    assert failure is not None
    assert failure.kind == "gate_failure"
    assert failure.step == "extract_claims"
    assert len([r for r in trace.records if r.step == "extract_claims"]) == 3
