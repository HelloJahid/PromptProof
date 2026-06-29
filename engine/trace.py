"""RunTrace — the observability spine.

Every chain step appends a StepRecord: which step ran, which attempt, the outcome, any retry
reason, the model used, token usage, and the wall-clock `seconds` it took. The seconds field
is what makes latency debuggable — `render()` shows per-step timing so you can see exactly
where a slow live run spends its time.

`record()` is guarded by a module-level lock so the chain can append from worker threads
(the per-claim searches run concurrently).
"""

from __future__ import annotations

import threading
from typing import Optional

from pydantic import BaseModel, Field

_RECORD_LOCK = threading.Lock()


class StepRecord(BaseModel):
    step: str
    attempt: int = 1
    outcome: str = "ok"  # "ok" | "gate_failed" | "retry" | "tool_failed" | "error"
    retry_reason: Optional[str] = None
    model: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    seconds: float = 0.0
    note: Optional[str] = None


class RunTrace(BaseModel):
    records: list[StepRecord] = Field(default_factory=list)

    def record(self, **kwargs) -> StepRecord:
        """Append and return a StepRecord. Thread-safe (searches run concurrently)."""
        rec = StepRecord(**kwargs)
        with _RECORD_LOCK:
            self.records.append(rec)
        return rec

    @property
    def total_input_tokens(self) -> int:
        return sum(r.input_tokens for r in self.records)

    @property
    def total_output_tokens(self) -> int:
        return sum(r.output_tokens for r in self.records)

    @property
    def total_seconds(self) -> float:
        return sum(r.seconds for r in self.records)

    def render(self) -> str:
        """A human-readable summary for the CLI `--trace` flag and the GUI trace panel."""
        lines = []
        for i, r in enumerate(self.records, start=1):
            extra = f" | retry: {r.retry_reason}" if r.retry_reason else ""
            lines.append(
                f"{i:>2}. {r.step:<18} attempt={r.attempt} outcome={r.outcome} "
                f"{r.seconds:5.1f}s tokens(in/out)={r.input_tokens}/{r.output_tokens}{extra}"
            )
        lines.append(
            f"    TOTAL tokens in/out = "
            f"{self.total_input_tokens}/{self.total_output_tokens}"
            f" | {self.total_seconds:.1f}s"
        )
        return "\n".join(lines)
