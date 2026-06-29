# PromptProof — Project Plan

> **Tagline:** PromptProof — a self-correcting prompting engine that verifies information by
> chaining focused prompts, gate-checking every step with Pydantic, grounding claims with a
> live search tool, and looping an LLM judge until the verdict holds up.

This file is the recovered, single source of truth for the project decisions and the build
plan. It captures the selected task, why it was chosen, the naming decision, and the phased
roadmap. (Reconstructed from the original chat after a folder rename orphaned the history.)

---

## 1. Project framing (from CLAUDE.md)

This is **entry #2** in an agentic-AI portfolio series (entry #1 was a CI/CD pipeline). The
**prompting engine is the star**; the concrete task is just "cargo" — one real, well-defined
job so the engine has something reliable to do.

Priority order, always:
1. **The prompting engine** — chained, gate-checked, feedback-looped, production-style.
2. **Reliability and observability** — validation, retries, structured errors, logging.
3. **The underlying task** — one real task, kept simple.

The engine must demonstrate four workflow mechanisms for real:
- **Prompt chaining** — decompose into focused, dependency-ordered steps.
- **Gate checks** — Pydantic validation between steps, with halt / retry / retry-with-feedback.
- **A gate-checked ReAct tool step** — external call whose raw response is schema-validated
  with a controlled retry, so a broken observation never corrupts the chain.
- **A feedback loop** — an evaluator (LLM-as-judge or rule-based) reviews output against
  criteria and loops until it passes or hits a cap.

Earlier single-prompt techniques (role-based prompting, CoT, the five refinement components —
role, task, format, examples, context) should appear naturally inside the individual prompts.

---

## 2. SELECTED TASK — Option 1: Grounded Claim Checker ✅

**"Paste a short paragraph; the engine fact-checks each claim against live web evidence and
returns a structured verdict report."**

Input is a few sentences of prose. The engine splits it into atomic checkable claims, searches
the web for evidence on each, judges each claim as **Supported / Refuted / Unverifiable** with
a citation, and produces a structured report. It iterates if the report is incomplete or weakly
evidenced.

### Worked example

Input:
> "The Sydney Opera House was designed by a Danish architect and opened in 1973. It has over
> 2,000 rooms and was funded entirely by the Australian federal government."

1. **Extract atomic claims** — split mashed-together facts into individually checkable ones:
   1. Designed by a Danish architect.
   2. Opened in 1973.
   3. Has over 2,000 rooms.
   4. Funded entirely by the Australian federal government.
2. **Find evidence per claim** (the external tool step) — web search each claim.
3. **Judge each claim against its evidence** — Supported / Refuted / Unverifiable + source.
4. **Return a structured report** — table of claim, verdict, source.

### Why this is the right cargo (needs all four mechanisms naturally)

- **Prompt chaining** — "extract claims", "search for evidence", "judge the claim" are three
  genuinely different jobs. One prompt does all three badly, so chaining is required, not decoration.
- **Gate checks (Pydantic)** — after extraction the engine must get a clean *list of claim
  objects*, not a rambling paragraph. A malformed result is caught and retried before it poisons
  the search step.
- **Gate-checked tool call** — web search is the riskiest part (timeouts, rate limits, junk,
  schema drift). The textbook "external tools fail more than the model" case. Validate the raw
  response and retry so a broken result never reaches judging.
- **Feedback loop (LLM-as-judge)** — judging "is this claim supported by this evidence?" *is*
  an LLM-as-judge call. An evaluator pass then checks the whole report: every claim has a
  verdict, every verdict cites a source, evidence is relevant — looping until pass or cap.

### Why on-trend (mid-2026)

- Structured outputs have replaced regex parsing; **Pydantic / Pydantic AI** is the dominant
  Python validation layer for agentic workflows.
- **LLM-as-judge** has gone from experimental to essential (judges agree with humans ~85%).
- **Self-correction** works best as *evaluation-driven* iteration against explicit external
  criteria, not naive "ask the model to fix itself" (which can reinforce its own biases).
- **Grounding / faithfulness / hallucination control** is the #1 reliability headline.

The reference doc's four mechanisms map almost one-to-one onto the four hottest 2026
reliability topics — a strong blog narrative.

### Rough chain

(1) extract atomic claims [CoT] → gate: list of well-formed claim objects → (2) ReAct search
per claim → **gate-checked tool call** on raw search results → (3) judge each claim vs evidence
[LLM-as-judge] → gate: every claim has verdict+citation → (4) feedback loop: evaluator checks
completeness/citation quality, sends back for another pass until pass or cap.

### External tool

**Tavily** (chosen) — a search API purpose-built for LLM/agent use: clean JSON, a real free
tier (~1,000 credits/month), single env-var key. Alternative considered: Brave (rawer JSON,
which would make the gate-check "tools fail more than the model" story more vivid). Rejected
for pedagogy: Anthropic's server-side `web_search` tool, because it hides the raw observation
inside the model and defeats the whole point of demonstrating a *gate-checked external tool
call*. Build `tools.py` against a **mocked** Tavily client from the start; sign up for the key
only at Phase 4. Never hardcode keys — env vars only.

---

## 3. Options considered (for the record)

- **Option 1 (CHOSEN) — Grounded claim checker.** Strongest current trend (grounding +
  LLM-as-judge); its external tool (web search) is the most failure-prone, making the
  gate-checked-tool reliability story the most compelling to write about.
- **Option 2 — Weather-aware day planner.** Uses **Open-Meteo** (free, no API key) — best
  reproducibility story and closest match to the reference doc's own weather-API example.
  The safe pick if zero-friction reproducibility mattered most.
- **Option 3 — Recipe builder with nutrition guardrails.** Most relatable, least on-trend;
  nicely mixes rule-based + LLM-judge feedback. Needs a nutrition API key (USDA / Nutritionix).

---

## 4. Naming decision — PromptProof ✅

Chosen because it fuses the two halves: **Prompt** (the engine, the star) + **Proof**
(information verification, the task). The "prompt-proof = robust/reliable" pun ties directly to
the blog's reliability thesis. Alliterative, memorable, self-explanatory.

- **Folder / repo slug:** `promptproof` (or `promptproof-engine` to stress the engine).
- Alternatives considered: VeriPrompt, ProofChain, PromptVerify, TruePrompt (and earlier,
  before the "must contain prompt" brief: VeriChain, Crucible, ClaimForge, Groundwork, Tribunal, Sift).
- **TODO:** confirm `promptproof` GitHub/PyPI slug availability before publishing.

---

## 5. Phased build plan

Mirrors the reference doc's arc (foundations → single prompt → chain → gates → tool → feedback
→ tests → interface → CI → blog). Each phase runs in the **What / Why / How → wait for "go" →
execute one phase → repeat** teaching loop, with a named git branch per phase.

| Phase | What we build | Doc technique it demonstrates |
|---|---|---|
| **0. Scaffolding** | Repo layout, `.gitignore` (`.env`, keys, caches), pinned `requirements`, `.env.example`, thin `llm.py` model abstraction with an **injectable client (mock mode)**, env-var key loading, plus the **`RunTrace`** observability object and typed error models (`GateFailure`/`ToolFailure`) introduced as the spine. Model IDs / structured-output APIs verified against live docs (done — see §6). | Foundations, system/user prompts |
| **1. One refined prompt** | The **claim-extraction** step alone — one prompt using all five refinement components (role/task/format/examples/context) + CoT. | Prompt instruction refinement, CoT |
| **2. Chain two steps** | Add the **judge** step fed by step 1, judging on the **model's own memory** (no evidence yet, no validation) — deliberately exposing hallucinated / unverifiable verdicts that motivate the Phase-4 search tool. | Prompt chaining |
| **3. Pydantic gate checks** | Insert typed schemas between steps with halt / retry / **retry-with-feedback**, kept *visible* (manual `model_validate` + feedback) rather than hidden inside SDK structured outputs. | Gate checks |
| **4. Gate-checked tool step** | Insert the **Tavily web-search** ReAct step *between* extract and judge; validate raw search responses against a schema with controlled retry; upgrade the judge to evidence-grounded. | ReAct + gate-checked tool call |
| **5. Feedback loop** | Add the **evaluator** (LLM-as-judge) that reviews the whole report against criteria and loops until pass or cap. | Feedback loops |
| **6. Tests + mini-eval** | pytest with model **and** search tool mocked (zero live calls); plus a small **golden-example** set (fixed paragraphs → expected verdicts) doubling as a lightweight eval. | Reliability |
| **7. Minimal interface** | A thin CLI (paste paragraph → report) with a `--trace` flag surfacing the `RunTrace`. | — |
| **8. Light CI** | GitHub Actions: lint + test only. | Hygiene |
| **9. Minimal GUI** | A thin **Streamlit** app (paste paragraph → cited verdict report) reusing `run_chain`; pure `report_to_markdown` for testability; GUI dep isolated in `requirements-gui.txt`. | — |
| **10. Blog** | Medium-ready post in `docs/blog/`, mostly about the engine. | Documentation |

### Cross-cutting engineering decisions (added after plan review)

- **Observability spine, not an afterthought.** A `RunTrace` records every step, attempt,
  gate result, retry reason, model, and token usage from Phase 0 — this *is* the reliability
  story the blog hinges on.
- **Typed structured errors.** Gates and tools return Pydantic `GateFailure` / `ToolFailure`
  objects the engine can reason about, not bare exceptions.
- **Testability seams from Phase 0.** `llm.py` and `tools.py` take an injectable client so
  the whole chain runs fully mocked with zero live calls.
- **Gate checks stay visible.** Native structured outputs are used (if at all) only as a
  *syntactic* safety net; an explicit Pydantic gate enforces *semantic* invariants (every
  claim has a citation, verdict ∈ enum, evidence non-empty) and drives retry-with-feedback,
  so the gate-check mechanism the blog showcases is never buried inside the SDK.

---

## 6. Decisions (resolved at plan review, 2026-06-27)

1. **Phase plan approved** with the 7 cross-cutting improvements above (observability spine,
   typed errors, testability seams, visible gate-checks, Phase-2 framing, mini-eval, hygiene).
2. **Provider / models = Anthropic.** `claude-sonnet-4-6` as the default chain model
   (cheap, fast, supports structured outputs + adaptive thinking); optionally `claude-opus-4-8`
   for the judge/evaluator. Behind the thin `llm.py` abstraction so it's a one-line change.
   (OpenAI was considered; the offered key only authenticated through a Vocareum course proxy,
   not native OpenAI — extra friction for a reproducible repo, so dropped.)
3. **Phase 4 search API = Tavily**, mocked until Phase 4 (sign up for the key then).
4. **Model/structured-output facts verified live** (CLAUDE.md §5): checked
   `platform.claude.com` models + structured-outputs docs and the bundled `claude-api` skill.
   Current IDs are dateless pinned snapshots (`claude-opus-4-8`, `claude-sonnet-4-6`,
   `claude-haiku-4-5` — no date suffixes). Structured outputs are GA via
   `client.messages.parse(output_format=PydanticModel)` → `response.parsed_output`;
   `output_format` is a still-supported alias for `output_config.format` (not deprecated).
   Adaptive thinking + `effort` replace `budget_tokens`. Keys from `ANTHROPIC_API_KEY` only.

---

## 7. Status

- [x] Reference doc read; trends researched.
- [x] Task chosen — Option 1, Grounded Claim Checker.
- [x] Name chosen — PromptProof.
- [x] Project folder renamed `prompt_engeering` → `PromptProof`.
- [x] Chat history recovered after rename orphaned it.
- [x] Phase plan approved (with 7 cross-cutting improvements).
- [x] Provider/model decision — Anthropic; Sonnet 4.6 default, Opus 4.8 for judge.
- [x] Phase 4 search-API decision — Tavily (mock until Phase 4).
- [x] Model/structured-output facts verified against live docs.
- [ ] Phase 0 — scaffolding.
