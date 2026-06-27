"""Typed, structured errors the engine can *reason about* rather than just crash on.

These are Pydantic models, not exceptions. Gates and tools return them so the
orchestrator can inspect a failure (e.g. feed `raw` back into a retry-with-feedback
prompt) instead of catching an opaque traceback. This is the "structured error
objects the engine can reason about" requirement from the project brief.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class EngineError(BaseModel):
    """Base structured error. `kind` is a stable machine-readable tag."""

    kind: str
    reason: str
    detail: Optional[str] = None


class GateFailure(EngineError):
    """A Pydantic gate-check rejected a step's output before it flowed downstream."""

    kind: str = "gate_failure"
    step: str
    raw: Optional[str] = None  # the offending raw output, for retry-with-feedback


class ToolFailure(EngineError):
    """An external tool call (e.g. web search) failed validation after its retries."""

    kind: str = "tool_failure"
    tool: str
    attempts: int = 0
