"""AE-5: Citation Correctness eval.

Checks whether each cited claim is actually supported by the paper it cites.
Uses an LLM judge to evaluate claim-citation alignment.

Matching strategy:
  - Numeric citations [N]: map to table row index N-1
  - Author-year citations: use match_citation_to_table()

Scoring:
  - supports = 1.0, partially_supports = 0.5, contradicts/unrelated = 0.0
  - final score = average across all cited claims
  - passed = score >= 0.7

Usage (standalone):
    python -m evals.artifact.citation_correctness samples/case_001/
"""

from __future__ import annotations

import re

from evals.shared.citation_parser import Citation, match_citation_to_table
from evals.shared.claim_extractor import extract_claims
from evals.shared.llm_judge import LLMJudge
from evals.shared.loader import CaseData, load_case
from evals.shared.results import EvalResult, Finding
from evals.shared.table_parser import PaperRecord, parse_table

# ---------------------------------------------------------------------------
# Eval metadata (consumed by the runner registry)
# ---------------------------------------------------------------------------

EVAL_NAME = "ae-5"
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


def _resolve_citation_to_paper(
    citation: Citation,
    table_rows: list[dict],
    paper_records: list[PaperRecord],
) -> PaperRecord | None:
    """Resolve a Citation to a PaperRecord using numeric or author-year matching.

    Args:
        citation: The Citation to resolve.
        table_rows: Raw table rows from CaseData.table (for match_citation_to_table).
        paper_records: Parsed PaperRecord objects (for indexed access).

    Returns:
        The matching PaperRecord, or None if no match found.
    """
    # Numeric reference: map [N] to table row index N-1.
    if citation.reference_id is not None and citation.authors is None:
        try:
            idx = int(citation.reference_id) - 1
            if 0 <= idx < len(paper_records):
                return paper_records[idx]
        except (ValueError, TypeError):
            pass
        return None

    # Author-year citation: use match_citation_to_table.
    matched_row = match_citation_to_table(citation, table_rows)
    if matched_row is None:
        return None

    # Find the PaperRecord that corresponds to this row.
    # We compare by title (which must be unique in the table).
    matched_title = matched_row.get("Title") or matched_row.get("title") or ""
    for record in paper_records:
        if record.title == matched_title:
            return record

    return None


def _build_correctness_prompt(claim_text: str, paper: PaperRecord) -> str:
    """Build the LLM prompt to judge whether the paper supports the claim."""
    abstract_snippet = (paper.abstract or "")[:500]
    focus_cols = "\n".join(f"  - {k}: {v}" for k, v in paper.focus_columns.items())

    return (
        "You are an expert scientific reviewer. "
        "Evaluate whether the cited paper supports the given claim.\n\n"
        f"**Claim:** {claim_text}\n\n"
        f"**Cited Paper:**\n"
        f"  Title: {paper.title}\n"
        f"  Authors: {paper.authors}\n"
        f"  Year: {paper.year}\n"
        f"  Abstract (excerpt): {abstract_snippet}\n"
        f"  Key data:\n{focus_cols}\n\n"
        "Does this paper support the claim?\n"
        "Choose one of the following verdicts:\n"
        '  - "supports": the paper directly supports the claim\n'
        '  - "partially_supports": the paper provides partial or indirect support\n'
        '  - "contradicts": the paper contradicts the claim\n'
        '  - "unrelated": the paper does not address the claim\n'
    )


# ---------------------------------------------------------------------------
# Public eval function
# ---------------------------------------------------------------------------

def evaluate_citation_correctness(case: CaseData) -> EvalResult:
    """Run the AE-5 citation-correctness eval on a loaded case.

    Returns an ``EvalResult`` with:
      - score = average of per-claim scores (supports=1.0, partially=0.5, else 0.0)
      - passed = True if score >= 0.7
      - one Finding per contradicts/unrelated verdict (error) or partially_supports (warning)
    """
    # Strip references section and extract claims.
    body = _strip_references_section(case.report)
    llm_judge = LLMJudge()
    claims = extract_claims(body, llm_judge)

    # Filter to cited claims only.
    cited_claims = [c for c in claims if c.citation is not None]

    if len(cited_claims) == 0:
        # No cited claims = nothing to evaluate = perfect score.
        return EvalResult(
            eval_name=EVAL_NAME,
            score=1.0,
            max_score=1.0,
            passed=True,
            findings=[],
            reasoning="No cited claims found in report. Nothing to evaluate.",
        )

    # Parse the table.
    paper_records = parse_table(str(case.case_path / "table.csv"))

    # Evaluate each cited claim.
    findings: list[Finding] = []
    scores: list[float] = []

    for claim in cited_claims:
        # Resolve citation to paper.
        paper = _resolve_citation_to_paper(
            claim.citation,  # type: ignore[arg-type]  # citation is not None here
            case.table,
            paper_records,
        )

        if paper is None:
            # Citation doesn't resolve to any paper (fabricated reference).
            # This is already handled by AE-6, but we flag it here too.
            findings.append(Finding(
                severity="error",
                message=f"Cannot resolve citation {claim.citation.raw_text} in claim: {claim.text}",  # type: ignore[union-attr]
                location=claim.section,
            ))
            scores.append(0.0)
            continue

        # Ask LLM judge whether the paper supports the claim.
        prompt = _build_correctness_prompt(claim.text, paper)
        response_schema = {
            "verdict": 'one of: "supports", "partially_supports", "contradicts", "unrelated"',
            "reasoning": "brief explanation",
        }
        response = llm_judge.judge(prompt, response_schema)

        verdict = response.get("verdict", "unrelated")
        reasoning = response.get("reasoning", "")

        # Map verdict to score.
        if verdict == "supports":
            score = 1.0
        elif verdict == "partially_supports":
            score = 0.5
            findings.append(Finding(
                severity="warning",
                message=f"Partial support: {claim.text} | Citation: {claim.citation.raw_text} | {reasoning}",  # type: ignore[union-attr]
                location=claim.section,
            ))
        elif verdict == "contradicts":
            score = 0.0
            findings.append(Finding(
                severity="error",
                message=f"Contradiction: {claim.text} | Citation: {claim.citation.raw_text} | {reasoning}",  # type: ignore[union-attr]
                location=claim.section,
            ))
        else:  # unrelated
            score = 0.0
            findings.append(Finding(
                severity="error",
                message=f"Unrelated citation: {claim.text} | Citation: {claim.citation.raw_text} | {reasoning}",  # type: ignore[union-attr]
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
            f"Evaluated {len(cited_claims)} cited claim(s). "
            f"Average correctness score: {final_score:.2f}"
        ),
    )


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m evals.artifact.citation_correctness <case_path>")
        sys.exit(1)

    case = load_case(sys.argv[1])
    result = evaluate_citation_correctness(case)
    print(f"AE-5 Citation Correctness")
    print(f"  Score:  {result.score}/{result.max_score}")
    print(f"  Passed: {result.passed}")
    print(f"  Reason: {result.reasoning}")
    if result.findings:
        print(f"  Findings ({len(result.findings)}):")
        for f in result.findings[:10]:  # Show first 10 only
            print(f"    [{f.severity}] {f.message[:120]}")
        if len(result.findings) > 10:
            print(f"    ... and {len(result.findings) - 10} more")
