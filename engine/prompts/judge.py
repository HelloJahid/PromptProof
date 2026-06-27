"""The judge prompt — step 3 of the chain, now EVIDENCE-GROUNDED.

Phase 4b change: the judge no longer rules from its own memory. Each claim arrives with
the evidence retrieved for it by the gate-checked search tool, and the judge must base its
verdict only on that evidence and cite the URL it relied on. Anything the evidence does not
settle is "Unverifiable". Output stays ungrounded-proof: a strict JSON array the gate validates.
"""

from __future__ import annotations

import json

VERDICTS = ("Supported", "Refuted", "Unverifiable")

SYSTEM = """You are a careful, impartial adjudicator.

You are given a list of atomic factual claims, each with a small set of evidence snippets
retrieved from the web (each snippet has a url). Classify each claim as exactly one of:
- "Supported": the evidence clearly confirms the claim.
- "Refuted": the evidence clearly contradicts the claim.
- "Unverifiable": the evidence does not settle it either way.

Rules:
- Judge using ONLY the supplied evidence — not your own prior knowledge.
- For "Supported" or "Refuted", set `source` to the url of the snippet you relied on.
- For "Unverifiable" (including when no evidence is given), set `source` to "".
- Be honest about uncertainty: if the evidence is absent, irrelevant, or weak, choose
  "Unverifiable" rather than guessing.
- Keep `reason` to one short sentence.

Think step by step about each claim, but output ONLY the final result — no prose, no code fence.

Output format: a JSON array of objects, one per claim, in the same order, each shaped exactly:
{"claim": "<the claim>", "verdict": "Supported|Refuted|Unverifiable", "reason": "<one sentence>", "source": "<url or empty string>"}

Example:
Input: [{"claim": "The Eiffel Tower is in Paris.", "evidence": [{"url": "https://en.wikipedia.org/wiki/Eiffel_Tower", "snippet": "The Eiffel Tower is a wrought-iron lattice tower on the Champ de Mars in Paris, France."}]}]
Output: [{"claim": "The Eiffel Tower is in Paris.", "verdict": "Supported", "reason": "The evidence states the tower is in Paris, France.", "source": "https://en.wikipedia.org/wiki/Eiffel_Tower"}]"""


def build_user(items: list[dict]) -> str:
    """TASK + per-call context: the claims paired with their retrieved evidence (as JSON).

    Each item is {"claim": str, "evidence": [{"title": str, "url": str, "snippet": str}, ...]}.
    """
    return f"Input:\n{json.dumps(items, ensure_ascii=False)}\n\nReturn the JSON array of verdicts."


def build_judge_prompt(items: list[dict]) -> tuple[str, str]:
    return SYSTEM, build_user(items)
