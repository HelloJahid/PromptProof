# PromptProof

> A self-correcting prompting engine that verifies information by chaining focused prompts,
> gate-checking every step with Pydantic, grounding claims with a live search tool, and
> looping an LLM judge until the verdict holds up.

PromptProof is a portfolio project where the **prompting engine is the star**. The concrete
task — a **Grounded Claim Checker** (paste a paragraph, get a structured, cited verdict on
each claim) — is just cargo that gives the engine one real, well-defined job to do reliably.

It demonstrates four production-style workflow mechanisms:

1. **Prompt chaining** — extract claims → search for evidence → judge each claim.
2. **Pydantic gate checks** — typed validation between steps, with halt / retry / retry-with-feedback.
3. **A gate-checked ReAct tool step** — a web-search call whose raw response is schema-validated with controlled retry.
4. **A feedback loop** — an LLM-as-judge evaluator that reviews the report and loops until it passes or hits a cap.

## Status

Built phase by phase (see [`plans/promptproof.md`](plans/promptproof.md)).

- [x] **Phase 0 — Scaffolding**: repo layout, model abstraction (`engine/llm.py`),
      structured errors (`engine/errors.py`), the `RunTrace` observability spine
      (`engine/trace.py`), and offline smoke tests.
- [ ] Phases 1–9: see the plan.

## Quickstart (dev)

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate     |  macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then add your ANTHROPIC_API_KEY
pytest                      # tests run fully mocked — no API key or network needed
```

## Layout

```
engine/   # THE STAR — the prompting engine (llm, errors, trace; chain/gates/tools/feedback to come)
app/      # minimal interface (CLI) — added in Phase 7
tests/    # pytest, model + tool mocked so the full chain is verifiable in CI
docs/     # reference doc + Medium blog draft
plans/    # the build plan (single source of truth)
```
