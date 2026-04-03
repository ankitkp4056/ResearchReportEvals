"""AE-2: Section Coverage eval.

Evaluates whether the generated report addresses all topic areas identified in
the research plan (todo.md). The eval uses an LLM judge to:
  1. Extract topic areas from the plan
  2. Determine coverage status (full/partial/missing) for each topic in the report
  3. Compute a coverage score

Note: Report sections may be reorganized, combined, or lack explicit headings.
The LLM matches by content, not heading text. Extra report sections
(e.g., Limitations, Future Research) do not penalize the score.

Usage (standalone):
    python -m evals.artifact.section_coverage samples/case_001/
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from evals.shared.llm_judge import LLMJudge
from evals.shared.loader import CaseData, load_case
from evals.shared.results import EvalResult, Finding

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Eval metadata (consumed by the runner registry)
# ---------------------------------------------------------------------------

EVAL_NAME = "ae-2"
REQUIRED_ARTIFACTS = ["plan", "report"]

# ---------------------------------------------------------------------------
# Public eval function
# ---------------------------------------------------------------------------

def evaluate_section_coverage(case: CaseData) -> EvalResult:
    """Run the AE-2 section coverage eval on a loaded case.

    Returns an ``EvalResult`` with:
      - score: coverage score (0.0-1.0) based on full/partial/missing topics
      - passed: True if score >= 0.75
      - findings: one per topic indicating coverage status
    """
    judge = LLMJudge()

    prompt = f"""You are evaluating whether a research report covers all topic areas outlined in a research plan.

**Research Plan (todo.md):**
{case.plan}

**Generated Report (report.md):**
{case.report}

Your task:
1. Identify all distinct research topic areas from the plan. Focus on substantive topics (not meta-sections like "Search Strategy" or "Deliverable").
2. For each topic, determine its coverage status in the report:
   - "full": The topic is thoroughly addressed with appropriate depth
   - "partial": The topic is mentioned but lacks depth or completeness
   - "missing": The topic is not addressed in the report

Important guidance:
- Report sections may be reorganized, combined, or renamed. Match by content, not by heading text.
- Extra report sections (e.g., Discussion, Limitations, Future Research) that are not in the plan do NOT count as problems.
- Focus on whether the plan's promised topics are actually delivered.

For each topic, provide:
- topic_name: Clear name for the topic
- coverage: One of "full", "partial", "missing"
- report_location: Where in the report this topic is addressed (section name or "N/A" if missing)"""

    response_schema = {
        "topics": "list of objects, each with keys: topic_name (string), coverage (one of full/partial/missing), report_location (string)",
        "reasoning": "brief explanation of your coverage assessment",
    }

    response = judge.judge(prompt, response_schema)

    # Parse topics and compute coverage score
    topics = response.get("topics", [])
    if not topics:
        return EvalResult(
            eval_name=EVAL_NAME,
            score=0.0,
            max_score=1.0,
            passed=False,
            findings=[Finding(
                severity="error",
                message="LLM returned no topics from the plan",
                location=None,
            )],
            reasoning="No topics identified in plan",
        )

    # Compute coverage score
    full_count = sum(1 for t in topics if t.get("coverage") == "full")
    partial_count = sum(1 for t in topics if t.get("coverage") == "partial")
    missing_count = sum(1 for t in topics if t.get("coverage") == "missing")

    total_topics = len(topics)
    score = (full_count * 1.0 + partial_count * 0.5) / total_topics
    passed = score >= 0.75

    # Build findings
    findings: list[Finding] = []
    for topic in topics:
        topic_name = topic.get("topic_name", "Unknown topic")
        coverage = topic.get("coverage", "missing")
        location = topic.get("report_location", "N/A")

        if coverage == "full":
            findings.append(Finding(
                severity="info",
                message=f"Topic fully covered: {topic_name}",
                location=location,
            ))
        elif coverage == "partial":
            findings.append(Finding(
                severity="warning",
                message=f"Topic partially covered: {topic_name}",
                location=location,
            ))
        else:  # missing
            findings.append(Finding(
                severity="error",
                message=f"Topic missing: {topic_name}",
                location=location,
            ))

    return EvalResult(
        eval_name=EVAL_NAME,
        score=score,
        max_score=1.0,
        passed=passed,
        findings=findings,
        reasoning=(
            f"{response.get('reasoning', '')}\n\n"
            f"Coverage: {full_count} full, {partial_count} partial, "
            f"{missing_count} missing out of {total_topics} topics"
        ),
    )


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m evals.artifact.section_coverage <case_path>")
        sys.exit(1)

    case = load_case(sys.argv[1])
    result = evaluate_section_coverage(case)
    print(f"AE-2 Section Coverage")
    print(f"  Score:  {result.score:.2f}/{result.max_score}")
    print(f"  Passed: {result.passed}")
    print(f"  Reason: {result.reasoning}")
    if result.findings:
        print(f"  Findings:")
        for f in result.findings:
            print(f"    [{f.severity}] {f.message}")
