"""RunTrace — the observability spine.

Every chain step appends a StepRecord: which step ran, which attempt, the outcome,
any retry reason, the model used, and token usage. This is what makes the engine's
reliability story *visible* — later the CLI's `--trace` flag will render it.

Kept deliberately simple (plain Pydantic) so it is easy to read in a blog post.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class StepRecord(BaseModel):
    step: str
    attempt: int = 1
    outcome: str = "ok"  # "ok" | "gate_failed" | "retry" | "error"
    retry_reason: Optional[str] = None
    model: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    note: Optional[str] = None


class RunTrace(BaseModel):
    records: list[StepRecord] = Field(default_factory=list)

    def record(self, **kwargs) -> StepRecord:
        """Append and return a StepRecord. Returns it so callers can read it back."""
        rec = StepRecord(**kwargs)
        self.records.append(rec)
        return rec

    @property
    def total_input_tokens(self) -> int:
        return sum(r.input_tokens for r in self.records)

    @property
    def total_output_tokens(self) -> int:
        return sum(r.output_tokens for r in self.records)

    def render(self) -> str:
        """A human-readable summary for the CLI `--trace` flag."""
        lines = []
        for i, r in enumerate(self.records, start=1):
            extra = f" | retry: {r.retry_reason}" if r.retry_reason else ""
            lines.append(
                f"{i:>2}. {r.step:<18} attempt={r.attempt} outcome={r.outcome} "
                f"tokens(in/out)={r.input_tokens}/{r.output_tokens}{extra}"
            )
        lines.append(
            f"    TOTAL tokens in/out = "
            f"{self.total_input_tokens}/{self.total_output_tokens}"
        )
        return "\n".join(lines)
