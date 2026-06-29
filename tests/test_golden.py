"""Phase 6 — golden-example mini-eval.

A small catalogue of representative inputs run end-to-end through the full engine with
scripted model + tool responses. It verifies the engine's *orchestration* is correct and
deterministic in CI. It is NOT a measure of a live model's accuracy — the model and search
are mocked on purpose; the scripted verdicts stand in for what a real model would return.
"""

import pytest

# (name, claims, expected verdict labels in order)
GOLDEN = [
    (
        "sydney_opera_house",
        [
            "The Sydney Opera House was designed by a Danish architect.",
            "The Sydney Opera House opened in 1973.",
            "The Sydney Opera House has over 2,000 rooms.",
            "The Sydney Opera House was funded entirely by the Australian federal government.",
        ],
        ["Supported", "Supported", "Refuted", "Refuted"],
    ),
    (
        "eiffel_tower_mixed",
        [
            "The Eiffel Tower is in Paris.",
            "The Eiffel Tower is made of aluminium.",
            "The Eiffel Tower receives exactly seven million visitors annually.",
        ],
        ["Supported", "Refuted", "Unverifiable"],
    ),
    (
        "two_claims",
        ["Water boils at 100 degrees Celsius at sea level.", "The sun orbits the Earth."],
        ["Supported", "Refuted"],
    ),
]


def _judge_round(claims: list[str], labels: list[str]) -> list[dict]:
    """Build a scripted, schema-valid judge response. Unverifiable -> empty source."""
    out = []
    for claim, verdict in zip(claims, labels):
        source = "" if verdict == "Unverifiable" else f"https://ex.com/{len(out) + 1}"
        out.append(
            {"claim": claim, "verdict": verdict, "reason": "per the evidence.", "source": source}
        )
    return out


@pytest.mark.parametrize("name,claims,labels", GOLDEN, ids=[c[0] for c in GOLDEN])
def test_golden_case_runs_end_to_end_and_passes_evaluation(run_scripted, name, claims, labels):
    judge = _judge_round(claims, labels)
    report, _client, transport = run_scripted(extract=claims, judge_rounds=[judge])

    assert report.ok, f"{name}: chain halted ({report.failure})"
    assert report.evaluation.passed, f"{name}: evaluation issues -> {report.evaluation.issues}"
    assert [v.verdict for v in report.verdicts] == labels
    assert [v.claim for v in report.verdicts] == claims
    assert len(transport.calls) == len(claims)  # one search per claim


def test_golden_suite_covers_all_three_verdict_labels():
    # Sanity: the catalogue actually exercises Supported, Refuted, and Unverifiable.
    seen = {label for _, _, labels in GOLDEN for label in labels}
    assert seen == {"Supported", "Refuted", "Unverifiable"}
