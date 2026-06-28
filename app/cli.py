"""Command-line interface: paste a paragraph, get a cited verdict report.

Usage:
    python -m app.cli "The Eiffel Tower opened in 1889 and is made of aluminium."
    echo "..." | python -m app.cli --trace

Reads ANTHROPIC_API_KEY (and TAVILY_API_KEY for live search) from the environment / .env.
"""

from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv

from engine.chain import Report, run_chain
from engine.llm import LLM


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="promptproof",
        description="Fact-check a paragraph's claims against live web evidence.",
    )
    parser.add_argument(
        "paragraph",
        nargs="?",
        help="The paragraph to check. If omitted, it is read from stdin.",
    )
    parser.add_argument("--trace", action="store_true", help="Print the run trace.")
    parser.add_argument("--model", default=None, help="Override the model id for all steps.")
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=2,
        dest="max_iterations",
        help="Max evaluate/revise iterations (default 2).",
    )
    return parser


def format_report(report: Report, *, show_trace: bool = False) -> str:
    """Render a Report as plain text. Pure — used by both the CLI and the tests."""
    lines: list[str] = []

    if not report.ok:
        f = report.failure
        lines.append(f"RUN HALTED: {f.kind} at {f.step} — {f.reason}")
        if show_trace:
            lines.append("")
            lines.append(report.trace.render())
        return "\n".join(lines)

    lines.append(f"Checked {len(report.claims)} claim(s):")
    lines.append("")
    for i, v in enumerate(report.verdicts, start=1):
        lines.append(f"{i}. [{v.verdict}] {v.claim}")
        lines.append(f"     reason: {v.reason}")
        if v.source:
            lines.append(f"     source: {v.source}")

    if report.evaluation is not None:
        status = "PASSED" if report.evaluation.passed else "INCOMPLETE"
        lines.append("")
        lines.append(f"Evaluation: {status}")
        for issue in report.evaluation.issues:
            lines.append(f"  - {issue}")

    if show_trace:
        lines.append("")
        lines.append("--- trace ---")
        lines.append(report.trace.render())

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    paragraph = (args.paragraph if args.paragraph is not None else sys.stdin.read()).strip()
    if not paragraph:
        parser.error("no paragraph provided (pass it as an argument or via stdin)")

    load_dotenv()  # load .env into the environment so the SDKs find the keys

    report = run_chain(
        paragraph,
        LLM(),
        model=args.model,
        max_iterations=args.max_iterations,
    )
    print(format_report(report, show_trace=args.trace))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
