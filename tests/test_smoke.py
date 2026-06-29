"""Phase 0 smoke tests — prove the spine works fully offline (no network, no API key)."""

from engine.errors import GateFailure
from engine.llm import LLM, LLMResponse, MockClient
from engine.trace import RunTrace


def test_mock_llm_returns_scripted_text_without_network():
    client = MockClient(responses=["ok"])
    llm = LLM(client=client)

    resp = llm.complete(system="sys", user="hello world", model="claude-sonnet-4-6")

    assert isinstance(resp, LLMResponse)
    assert resp.text == "ok"
    assert resp.output_tokens == 1  # "ok" -> one token by the proxy counter
    # The engine's prompt is captured so later phases can assert on what was sent.
    assert client.calls[0]["user"] == "hello world"
    assert client.calls[0]["model"] == "claude-sonnet-4-6"


def test_llm_falls_back_to_default_response_when_script_exhausted():
    client = MockClient(default="DEFAULT")
    llm = LLM(client=client)
    assert llm.complete(system="s", user="u").text == "DEFAULT"


def test_run_trace_accumulates_tokens_and_renders():
    trace = RunTrace()
    trace.record(step="extract", input_tokens=10, output_tokens=5)
    trace.record(step="judge", input_tokens=20, output_tokens=8, outcome="ok")

    assert trace.total_input_tokens == 30
    assert trace.total_output_tokens == 13
    rendered = trace.render()
    assert "extract" in rendered and "judge" in rendered
    assert "TOTAL tokens in/out = 30/13" in rendered


def test_gate_failure_is_a_structured_object():
    err = GateFailure(step="extract", reason="output was not valid JSON", raw="{bad")
    assert err.kind == "gate_failure"
    assert err.step == "extract"
    assert err.raw == "{bad"
    # It is data, not an exception — the engine can inspect and act on it.
    assert "JSON" in err.reason
