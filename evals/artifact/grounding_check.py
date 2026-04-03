"""AE-7: Grounding Check eval.

Checks whether every claim in the report (cited or uncited) is grounded in at
least one of the source papers. This is a hallucination detector — claims that
have no grounding in any retrieved paper are flagged as errors.

Scoring:
  - grounded = 1.0, partially_grounded = 0.5, ungrounded = 0.0
  - final score = average across all claims
  - passed = score >= 0.7

Usage (standalone):
    python -m evals.artifact.grounding_check samples/case_001/
"""

from __future__ import annotations

import re

from evals.shared.claim_extractor import extract_claims
from evals.shared.llm_judge import LLMJudge
from evals.shared.loader import CaseData, load_case
from evals.shared.results import EvalResult, Finding
from evals.shared.table_parser import PaperRecord, parse_table

# ---------------------------------------------------------------------------
# Eval metadata (consumed by the runner registry)
# ---------------------------------------------------------------------------

EVAL_NAME = "ae-7"
REQUIRED_ARTIFACTS = ["report", "table"]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REFERENCES_HEADING_RE = re.compile(
    r"^#{1,6}\s+references\s*$", re.IGNORECASE | re.MULTILINE
)


def _strip_references_section(report: str) -> str:
    """Return the report text up to (but not including) the References heading."""
    m = _REFERENCES_HEADING_RE.search(report)
    if m is None:
        return report
    return report[: m.start()]


def _build_paper_summaries(paper_records: list[PaperRecord]) -> str:
    """Build a concise text summary of all papers for the LLM prompt.

    Each paper gets:
      - Title, Authors, Year
      - Abstract snippet (first ~200 chars)
      - Focus column values

    This keeps the prompt manageable even with 30+ papers.
    """
    summaries: list[str] = []
    for i, paper in enumerate(paper_records, start=1):
        abstract_snippet = (paper.abstract or "")[:200]
        if len(paper.abstract or "") > 200:
            abstract_snippet += "..."

        focus_lines = "\n    ".join(
            f"{k}: {v}" for k, v in paper.focus_columns.items()
        )

        summaries.append(
            f"[{i}] {paper.title}\n"
            f"  Authors: {paper.authors}\n"
            f"  Year: {paper.year}\n"
            f"  Abstract: {abstract_snippet}\n"
            f"  Key data:\n    {focus_lines}"
        )

    return "\n\n".join(summaries)


def _build_grounding_prompt(claim_text: str, paper_summaries: str) -> str:
    """Build the LLM prompt to judge whether the claim is grounded in source papers."""
    return (
        "You are an expert scientific reviewer. "
        "Evaluate whether the given claim is grounded in any of the provided source papers.\n\n"
        f"**Claim:** {claim_text}\n\n"
        "**Source Papers:**\n\n"
        f"{paper_summaries}\n\n"
        "Is this claim grounded in the source papers?\n"
        "Choose one of the following verdicts:\n"
        '  - "grounded": the claim is directly supported by one or more papers\n'
        '  - "partially_grounded": the claim has partial or indirect support\n'
        '  - "ungrounded": the claim has no support in any of the papers (hallucination)\n'
    )


# ---------------------------------------------------------------------------
# Public eval function
# ---------------------------------------------------------------------------

def evaluate_grounding_check(case: CaseData) -> EvalResult:
    """Run the AE-7 grounding-check eval on a loaded case.

    Returns an ``EvalResult`` with:
      - score = average of per-claim scores (grounded=1.0, partially=0.5, ungrounded=0.0)
      - passed = True if score >= 0.7
      - one Finding per ungrounded claim (error) or partially_grounded claim (warning)
    """
    # Strip references section and extract all claims.
    body = _strip_references_section(case.report)
    llm_judge = LLMJudge()
    claims = extract_claims(body, llm_judge)

    if len(claims) == 0:
        # No claims = nothing to evaluate = perfect score.
        return EvalResult(
            eval_name=EVAL_NAME,
            score=1.0,
            max_score=1.0,
            passed=True,
            findings=[],
            reasoning="No claims found in report. Nothing to evaluate.",
        )

    # Parse the table and build paper summaries once.
    paper_records = parse_table(str(case.case_path / "table.csv"))
    paper_summaries = _build_paper_summaries(paper_records)

    # Evaluate each claim against all papers.
    findings: list[Finding] = []
    scores: list[float] = []

    for claim in claims:
        prompt = _build_grounding_prompt(claim.text, paper_summaries)
        response_schema = {
            "verdict": 'one of: "grounded", "partially_grounded", "ungrounded"',
            "reasoning": "brief explanation",
        }
        response = llm_judge.judge(prompt, response_schema)

        verdict = response.get("verdict", "ungrounded")
        reasoning = response.get("reasoning", "")

        # Map verdict to score.
        if verdict == "grounded":
            score = 1.0
        elif verdict == "partially_grounded":
            score = 0.5
            findings.append(Finding(
                severity="warning",
                message=f"Partially grounded: {claim.text} | {reasoning}",
                location=claim.section,
            ))
        else:  # ungrounded
            score = 0.0
            findings.append(Finding(
                severity="error",
                message=f"Ungrounded claim (hallucination): {claim.text} | {reasoning}",
                location=claim.section,
            ))

        scores.append(score)

    # Compute final score.
    final_score = sum(scores) / len(scores)
    passed = final_score >= 0.7

    return EvalResult(
        eval_name=EVAL_NAME,
        score=final_score,
        max_score=1.0,
        passed=passed,
        findings=findings,
        reasoning=(
            f"Evaluated {len(claims)} claim(s) against {len(paper_records)} paper(s). "
            f"Average grounding score: {final_score:.2f}"
        ),
    )


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m evals.artifact.grounding_check <case_path>")
        sys.exit(1)

    case = load_case(sys.argv[1])
    result = evaluate_grounding_check(case)
    print(f"AE-7 Grounding Check")
    print(f"  Score:  {result.score}/{result.max_score}")
    print(f"  Passed: {result.passed}")
    print(f"  Reason: {result.reasoning}")
    if result.findings:
        print(f"  Findings ({len(result.findings)}):")
        for f in result.findings[:10]:  # Show first 10 only
            print(f"    [{f.severity}] {f.message[:120]}")
        if len(result.findings) > 10:
            print(f"    ... and {len(result.findings) - 10} more")
