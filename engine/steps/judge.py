"""Step 2 — judge each claim Supported / Refuted / Unverifiable.

Still ungated (Phase 3 adds the Pydantic gate). The naive parser mirrors the one in
`steps/extract.py`; both get replaced by a real gate check soon, so the small
duplication is intentional scaffolding.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

from engine.llm import LLM
from engine.prompts.judge import build_judge_prompt
from engine.trace import RunTrace


@dataclass
class Verdict:
    claim: str
    verdict: str
    reason: str


@dataclass
class JudgeResult:
    raw: str
    verdicts: list[Verdict]


def _parse_verdicts(text: str) -> list[Verdict]:
    """Best-effort, ungated parse of the verdict array. Returns [] on bad output."""
    s = text.strip()
    if s.startswith("```"):
        s = s.strip("`")
        if "[" in s:
            s = s[s.find("[") :]
    try:
        data = json.loads(s)
    except json.JSONDecodeError:
        i, j = s.find("["), s.rfind("]")
        if i != -1 and j > i:
            try:
                data = json.loads(s[i : j + 1])
            except json.JSONDecodeError:
                return []
        else:
            return []
    if not isinstance(data, list):
        return []
    out: list[Verdict] = []
    for item in data:
        if isinstance(item, dict) and "claim" in item and "verdict" in item:
            out.append(
                Verdict(
                    claim=str(item.get("claim", "")),
                    verdict=str(item.get("verdict", "")),
                    reason=str(item.get("reason", "")),
                )
            )
    return out


def judge_claims(
    claims: list[str],
    llm: LLM,
    *,
    trace: Optional[RunTrace] = None,
    model: Optional[str] = None,
    max_tokens: int = 1200,
) -> JudgeResult:
    system, user = build_judge_prompt(claims)
    resp = llm.complete(system=system, user=user, model=model, max_tokens=max_tokens)
    if trace is not None:
        trace.record(
            step="judge_claims",
            model=resp.model,
            input_tokens=resp.input_tokens,
            output_tokens=resp.output_tokens,
        )
    return JudgeResult(raw=resp.text, verdicts=_parse_verdicts(resp.text))
