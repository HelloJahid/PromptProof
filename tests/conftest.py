"""Shared test fixtures.

`run_scripted` builds a fully-mocked engine run: a MockClient scripted with the extract
and judge responses, plus a fake search transport. It returns the Report and the mock
objects so tests can assert on both the outcome and what the engine sent. Zero network,
no API keys.
"""

from __future__ import annotations

import json

import pytest

from engine.chain import run_chain
from engine.llm import LLM, MockClient


class FakeSearch:
    """Deterministic search transport: one evidence result per query."""

    def __init__(self, snippet: str = "evidence snippet"):
        self.snippet = snippet
        self.calls: list[str] = []

    def __call__(self, query, *, max_results=3):
        self.calls.append(query)
        return {
            "results": [
                {
                    "title": "src",
                    "url": f"https://ex.com/{len(self.calls)}",
                    "content": self.snippet,
                }
            ]
        }


@pytest.fixture
def run_scripted():
    """Factory: run the full chain against scripted extract + judge round(s)."""

    def _run(*, extract, judge_rounds, paragraph="A paragraph.", max_iterations=2):
        responses = [json.dumps(extract)] + [json.dumps(r) for r in judge_rounds]
        client = MockClient(responses=responses)
        transport = FakeSearch()
        report = run_chain(
            paragraph,
            LLM(client=client),
            transport=transport,
            max_iterations=max_iterations,
        )
        return report, client, transport

    return _run
