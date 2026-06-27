"""The judge prompt — step 2 of the chain.

Phase 2 note: the judge rules on each claim using ONLY the model's own knowledge —
there is no web evidence yet. This is deliberate. Ungrounded judging will sometimes
hallucinate or over-confidently mislabel claims, which is exactly the weakness the
Phase-4 search tool exists to fix. Like Phase 1, the output is also ungated (Phase 3
adds the Pydantic gate).
"""

from __future__ import annotations

import json

VERDICTS = ("Supported", "Refuted", "Unverifiable")

SYSTEM = """You are a careful, impartial adjudicator.

You are given a list of atomic factual claims. Classify each one as exactly one of:
- "Supported": you are confident the claim is true.
- "Refuted": you are confident the claim is false.
- "Unverifiable": you cannot confidently decide either way.

Rules:
- Judge using only your own knowledge for now; you have no external evidence.
- Be honest about uncertainty. If you are not confident, choose "Unverifiable" rather
  than guessing — an overconfident wrong verdict is worse than admitting uncertainty.
- Keep `reason` to one short sentence.

Think step by step about each claim, but output ONLY the final result — no prose, no
code fence.

Output format: a JSON array of objects, one per claim, in the same order, each shaped
exactly: {"claim": "<the claim>", "verdict": "Supported|Refuted|Unverifiable", "reason": "<one sentence>"}

Example:
Claims: ["The Eiffel Tower is in Paris.", "The Eiffel Tower is made of aluminium."]
Output: [{"claim": "The Eiffel Tower is in Paris.", "verdict": "Supported", "reason": "The Eiffel Tower is a well-known Paris landmark."}, {"claim": "The Eiffel Tower is made of aluminium.", "verdict": "Refuted", "reason": "It is built from puddled wrought iron, not aluminium."}]"""


def build_user(claims: list[str]) -> str:
    """TASK + per-call context (the claims to judge, as JSON)."""
    return f"Claims:\n{json.dumps(claims, ensure_ascii=False)}\n\nReturn the JSON array of verdicts."


def build_judge_prompt(claims: list[str]) -> tuple[str, str]:
    return SYSTEM, build_user(claims)
