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

The engine and both interfaces are complete (see [`plans/promptproof.md`](plans/promptproof.md)).
All four mechanisms are implemented and covered by offline tests (model + search mocked).

- [x] Scaffolding + observability spine (`engine/llm.py`, `engine/errors.py`, `engine/trace.py`)
- [x] Prompt chaining (`engine/chain.py`): extract → search → judge
- [x] Pydantic gate checks with halt / retry / retry-with-feedback (`engine/gates.py`)
- [x] Gate-checked ReAct web-search tool (`engine/tools.py`)
- [x] Evaluator feedback loop (`engine/feedback.py`)
- [x] Golden-example mini-eval, CLI (`app/cli.py`), Streamlit GUI (`app/gui.py`), CI
- [ ] Blog write-up (`docs/blog/`)

## Quickstart (dev)

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate     |  macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then add your ANTHROPIC_API_KEY (and TAVILY_API_KEY for live search)
pytest                      # tests run fully mocked — no API key or network needed
```

## Run it

Live runs read `ANTHROPIC_API_KEY` and `TAVILY_API_KEY` from `.env`.

**CLI**

```bash
python -m app.cli "The Sydney Opera House was designed by a Danish architect and opened in 1973."
# add --trace to see every step, retry, and evaluation
```

**GUI (Streamlit)**

```bash
pip install -r requirements-gui.txt
streamlit run app/gui.py     # opens http://localhost:8501 in your browser
```

## Layout

```
engine/   # THE STAR — the prompting engine (llm, errors, trace, chain, gates, tools, feedback)
app/      # minimal interfaces: cli.py (terminal) and gui.py (Streamlit)
tests/    # pytest, model + tool mocked so the full chain is verifiable in CI
plans/    # the build plan (single source of truth)
```
