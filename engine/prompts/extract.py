"""The claim-extraction prompt — the first link of the chain.

This is a worked demonstration of *prompt instruction refinement*: every one of the
five components is present and labelled in comments so the blog can point at them.
Chain-of-Thought is invited internally, but the model must output only the JSON result.
"""

from __future__ import annotations

# ROLE + CONTEXT + FORMAT + EXAMPLES live in the system prompt (stable across calls).
SYSTEM = """You are a meticulous fact-checking analyst.

Your job is to break a short paragraph into atomic claims — each a single,
self-contained, individually verifiable factual assertion.

Rules:
- One verifiable fact per claim. Split sentences that bundle several facts.
- Keep each claim self-contained: resolve pronouns (it, they, this) to what they refer to.
- Include only factual assertions. Drop opinions, questions, and filler.
- Preserve the original meaning; never add facts that were not stated.

Think step by step about where a single sentence hides several facts, but output
ONLY the final result — no reasoning, no prose, no code fence.

Output format: a JSON array of strings, and nothing else. Shape: ["claim one", "claim two"]

Example:
Paragraph: "The Sydney Opera House was designed by a Danish architect and opened in
1973. It has over 2,000 rooms and was funded entirely by the Australian federal
government."
Output: ["The Sydney Opera House was designed by a Danish architect.", "The Sydney Opera House opened in 1973.", "The Sydney Opera House has over 2,000 rooms.", "The Sydney Opera House was funded entirely by the Australian federal government."]"""


def build_user(paragraph: str) -> str:
    """The TASK + the per-call context (the actual paragraph)."""
    return f"Paragraph:\n{paragraph}\n\nReturn the JSON array of atomic claims."


def build_extract_prompt(paragraph: str) -> tuple[str, str]:
    """Return (system, user) for the extraction step."""
    return SYSTEM, build_user(paragraph)
