"""Streamlit GUI for PromptProof — a minimal browser front end over the engine.

Run it with:
    pip install -r requirements-gui.txt
    streamlit run app/gui.py

A thin layer over `engine.chain.run_chain`, mirroring `app/cli.py`. The engine is the star;
this just renders its Report. Streamlit is imported lazily inside `main()` so the pure
renderer (`report_to_markdown`) and `analyse()` stay importable in tests without Streamlit.
"""

from __future__ import annotations

from typing import Optional

from dotenv import load_dotenv

from engine.chain import Report, run_chain
from engine.llm import LLM
from engine.tools import Transport, tavily_transport

VERDICT_BADGE = {
    "Supported": "✅ **Supported**",
    "Refuted": "❌ **Refuted**",
    "Unverifiable": "❓ **Unverifiable**",
}

PLACEHOLDER = "The Sydney Opera House was designed by a Danish architect and opened in 1973."


def report_to_markdown(report: Report) -> str:
    """Render a Report as Markdown (pure — no Streamlit). Used by the UI and the tests."""
    if not report.ok:
        f = report.failure
        return f"### ⚠️ Run halted\n\n`{f.kind}` at **{f.step}** — {f.reason}"

    lines = [f"### Checked {len(report.claims)} claim(s)\n"]
    for v in report.verdicts:
        badge = VERDICT_BADGE.get(v.verdict, v.verdict)
        lines.append(f"{badge} — {v.claim}")
        lines.append(f"> {v.reason}")
        if v.source:
            lines.append(f"> [source]({v.source})")
        lines.append("")

    if report.evaluation is not None:
        if report.evaluation.passed:
            lines.append("**Evaluation:** ✅ passed")
        else:
            lines.append("**Evaluation:** ⚠️ incomplete")
            for issue in report.evaluation.issues:
                lines.append(f"- {issue}")

    return "\n".join(lines)


def analyse(
    paragraph: str,
    *,
    llm: Optional[LLM] = None,
    transport: Optional[Transport] = None,
    max_iterations: int = 2,
) -> Report:
    """Run the engine on a paragraph. Defaults to live clients; tests inject mocks."""
    return run_chain(
        paragraph,
        llm if llm is not None else LLM(),
        transport=transport if transport is not None else tavily_transport,
        max_iterations=max_iterations,
    )


def main() -> None:
    import streamlit as st

    load_dotenv()

    st.set_page_config(page_title="PromptProof", page_icon="✅")
    st.title("PromptProof")
    st.caption("Paste a paragraph. Each claim is checked against live web evidence.")

    paragraph = st.text_area("Paragraph", height=160, placeholder=PLACEHOLDER)

    if st.button("Check claims", type="primary"):
        if not paragraph.strip():
            st.warning("Please paste a paragraph first.")
            return
        with st.spinner("Extracting claims, searching for evidence, judging…"):
            report = analyse(paragraph.strip())
        st.markdown(report_to_markdown(report))
        with st.expander("Run trace"):
            st.code(report.trace.render())


if __name__ == "__main__":
    main()
