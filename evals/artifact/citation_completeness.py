"""AE-4: Citation Completeness eval.

Checks what fraction of factual claims in the report have accompanying citations.
Claims without citations are flagged as warnings.

Scoring:
  - score = (number of cited claims) / (total claims)
  - passed = score >= 0.8

Usage (standalone):
    python -m evals.artifact.citation_completeness samples/case_001/
"""

from __future__ import annotations

import re

from evals.shared.claim_extractor import extract_claims
from evals.shared.llm_judge import LLMJudge
from evals.shared.loader import CaseData, load_case
from evals.shared.results import EvalResult, Finding

# ---------------------------------------------------------------------------
# Eval metadata (consumed by the runner registry)
# ---------------------------------------------------------------------------

EVAL_NAME = "ae-4"
REQUIRED_ARTIFACTS = ["report"]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REFERENCES_HEADING_RE = re.compile(
    r"^#{1,6}\s+references\s*$", re.IGNORECASE | re.MULTILINE
)


def _strip_references_section(report: str) -> str:
    """Return the report text up to (but not including) the References heading.

    If no References heading is found, the full report is returned.
    """
    m = _REFERENCES_HEADING_RE.search(report)
    if m is None:
        return report
    return report[: m.start()]


# ---------------------------------------------------------------------------
# Public eval function
# ---------------------------------------------------------------------------

def evaluate_citation_completeness(case: CaseData) -> EvalResult:
    """Run the AE-4 citation-completeness eval on a loaded case.

    Returns an ``EvalResult`` with:
      - score = (cited claims) / (total claims) or 1.0 if no claims
      - passed = True if score >= 0.8
      - one Finding (severity="warning") per uncited claim
    """
    # Strip the references section before extracting claims.
    body = _strip_references_section(case.report)

    # Extract claims using LLMJudge.
    llm_judge = LLMJudge()
    claims = extract_claims(body, llm_judge)

    # Partition claims into cited vs. uncited.
    cited_claims = [c for c in claims if c.citation is not None]
    uncited_claims = [c for c in claims if c.citation is None]

    total_count = len(claims)
    cited_count = len(cited_claims)

    # Compute score.
    if total_count == 0:
        score = 1.0  # No claims = nothing to cite = perfect score
    else:
        score = cited_count / total_count

    # Create findings for uncited claims.
    findings: list[Finding] = []
    for claim in uncited_claims:
        findings.append(Finding(
            severity="warning",
            message=f"Uncited claim: {claim.text}",
            location=claim.section,
        ))

    passed = score >= 0.8

    return EvalResult(
        eval_name=EVAL_NAME,
        score=score,
        max_score=1.0,
        passed=passed,
        findings=findings,
        reasoning=(
            f"Extracted {total_count} claim(s). "
            f"{cited_count} have citations, {len(uncited_claims)} do not. "
            f"Completeness: {score:.2f}"
        ),
    )


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m evals.artifact.citation_completeness <case_path>")
        sys.exit(1)

    case = load_case(sys.argv[1])
    result = evaluate_citation_completeness(case)
    print(f"AE-4 Citation Completeness")
    print(f"  Score:  {result.score}/{result.max_score}")
    print(f"  Passed: {result.passed}")
    print(f"  Reason: {result.reasoning}")
    if result.findings:
        print(f"  Findings ({len(result.findings)}):")
        for f in result.findings[:10]:  # Show first 10 only
            print(f"    [{f.severity}] {f.message}")
        if len(result.findings) > 10:
            print(f"    ... and {len(result.findings) - 10} more")
