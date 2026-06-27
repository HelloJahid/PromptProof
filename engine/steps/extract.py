"""Step 1 — extract atomic claims from a paragraph.

Phase 1 deliberately has **no Pydantic gate yet**. It best-effort parses the model's
JSON and silently yields an empty list when the output is malformed. That fragility is
the point: Phase 3 replaces `_naive_parse` with a real gate check + retry-with-feedback,
and the contrast is what the blog uses to motivate gate checks.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

from engine.llm import LLM
from engine.prompts.extract import build_extract_prompt
from engine.trace import RunTrace


@dataclass
class ExtractResult:
    raw: str  # the model's raw text, kept for tracing / Phase-3 retry feedback
    claims: list[str]


def _naive_parse(text: str) -> list[str]:
    """Best-effort, ungated parse. Returns [] on anything it can't cleanly read."""
    s = text.strip()
    if s.startswith("```"):  # tolerate an accidental ```json ... ``` fence
        s = s.strip("`")
        if "[" in s:
            s = s[s.find("[") :]
    try:
        data = json.loads(s)
    except json.JSONDecodeError:
        i, j = s.find("["), s.rfind("]")  # last resort: slice the first [...] block
        if i != -1 and j > i:
            try:
                data = json.loads(s[i : j + 1])
            except json.JSONDecodeError:
                return []
        else:
            return []
    if isinstance(data, list) and all(isinstance(x, str) for x in data):
        return data
    return []


def extract_claims(
    paragraph: str,
    llm: LLM,
    *,
    trace: Optional[RunTrace] = None,
    model: Optional[str] = None,
    max_tokens: int = 800,
) -> ExtractResult:
    system, user = build_extract_prompt(paragraph)
    resp = llm.complete(system=system, user=user, model=model, max_tokens=max_tokens)
    if trace is not None:
        trace.record(
            step="extract_claims",
            model=resp.model,
            input_tokens=resp.input_tokens,
            output_tokens=resp.output_tokens,
        )
    return ExtractResult(raw=resp.text, claims=_naive_parse(resp.text))
