"""AE-6: Fabricated References eval.

Checks whether every inline citation in the report can be traced back to a
paper in the agent's extraction table.  Citations that cannot be matched are
flagged as fabricated.

Matching strategy:
  - Numeric citations [N]: verify that table row index N-1 exists (the table
    rows are ordered to match the reference numbering).
  - Author-year citations: delegate to ``match_citation_to_table()`` which
    performs case-insensitive author+year matching against the raw table.

Usage (standalone):
    python -m evals.artifact.fabricated_references samples/case_001/
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from evals.shared.citation_parser import Citation, extract_citations, match_citation_to_table
from evals.shared.loader import CaseData, load_case
from evals.shared.results import EvalResult, Finding

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Eval metadata (consumed by the runner registry)
# ---------------------------------------------------------------------------

EVAL_NAME = "ae-6"
REQUIRED_ARTIFACTS = ["report", "table"]

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


def _citation_matches_table(citation: Citation, table: list[dict]) -> bool:
    """Return True if *citation* can be resolved to a table row."""
    # Numeric reference: map [N] -> table row index N-1.
    if citation.reference_id is not None and citation.authors is None:
        try:
            idx = int(citation.reference_id) - 1
            return 0 <= idx < len(table)
        except (ValueError, TypeError):
            return False

    # Author-year citation: delegate to the parser's matching logic.
    return match_citation_to_table(citation, table) is not None


# ---------------------------------------------------------------------------
# Public eval function
# ---------------------------------------------------------------------------

def evaluate_fabricated_references(case: CaseData) -> EvalResult:
    """Run the AE-6 fabricated-references eval on a loaded case.

    Returns an ``EvalResult`` with:
      - score 1.0 and passed=True  if every citation resolves to the table
      - score 0.0 and passed=False if any citation is unmatched (fabricated)
      - one Finding (severity="error") per fabricated citation
    """
    body = _strip_references_section(case.report)
    citations = extract_citations(body)
    table = case.table

    findings: list[Finding] = []
    for cit in citations:
        if not _citation_matches_table(cit, table):
            findings.append(Finding(
                severity="error",
                message=f"Fabricated reference: {cit.raw_text} has no matching paper in the table",
                location=cit.raw_text,
            ))

    score = 1.0 if not findings else 0.0
    passed = len(findings) == 0

    return EvalResult(
        eval_name=EVAL_NAME,
        score=score,
        max_score=1.0,
        passed=passed,
        findings=findings,
        reasoning=(
            f"Checked {len(citations)} inline citation(s) against "
            f"{len(table)} table row(s). "
            f"{len(findings)} fabricated reference(s) found."
        ),
    )


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m evals.artifact.fabricated_references <case_path>")
        sys.exit(1)

    case = load_case(sys.argv[1])
    result = evaluate_fabricated_references(case)
    print(f"AE-6 Fabricated References")
    print(f"  Score:  {result.score}/{result.max_score}")
    print(f"  Passed: {result.passed}")
    print(f"  Reason: {result.reasoning}")
    if result.findings:
        print(f"  Findings:")
        for f in result.findings:
            print(f"    [{f.severity}] {f.message}")
