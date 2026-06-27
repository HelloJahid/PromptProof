# PromptProof — Starting Prompt for a New Chat

Paste the block below into a fresh Claude Code chat opened in this project folder.
It gets Claude up to speed, lets it propose professional improvements, and locks in
the teaching loop from CLAUDE.md.

---

## Full starting prompt (paste this)

```
Before doing anything else, read these two files in full and treat them as the
source of truth for this project:

1. CLAUDE.md  — the project instructions and how I want you to work with me.
2. plans/promptproof.md  — the recovered project plan: the chosen task (Option 1, Grounded Claim Checker), the name (PromptProof), the reasoning, and the 10-phase build roadmap.

Also read docs/llm_prompting_systems.md (the reference doc) if you haven't, since the engine must embody its arc.

Then, DO NOT write any code yet. Instead:

1. Give me a short summary proving you understand the project — what PromptProof is, why the prompting engine (not the task) is the star, and the four mechanisms it must demonstrate (prompt chaining, Pydantic gate checks, a gate-checked ReAct tool step, and a feedback loop).

2. Review the phased plan in plans/promptproof.md. If you see ways to make the project more complete, more reliable, or more professional portfolio-grade, propose those changes clearly — explain what you'd add or reorder and why. If you change the plan, update plans/promptproof.md so it stays the single source of truth.

3. Confirm the open decisions before we build:
   - Do you agree with the phase plan (with your proposed tweaks)?
   - The Phase 4 web-search API: recommend the cleanest free option and whether
     to sign up now or mock it until Phase 4.
   - Per CLAUDE.md section 5, before any model-API code, verify current model IDs
     and structured-output features against live provider docs and tell me what
     you checked. Do not trust memory.

4. Then STOP and wait for my approval.

Throughout this project, work in the teaching loop from CLAUDE.md section 7: for every step give me WHAT / WHY / HOW in beginner-friendly language, then STOP and wait for me to say "go" before executing. One phase at a time, never bundle
steps, never write code before the explanation. Tell me which git branch to use
per phase.
```

