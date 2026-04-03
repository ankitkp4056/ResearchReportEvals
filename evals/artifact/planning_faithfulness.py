"""AE-1: Planning Faithfulness eval.

Evaluates whether the planning document (todo.md) captures the user's research
question, identifies the correct purpose (survey/comparison/deep-dive), and
sets an appropriate scope for the query.

Uses LLMJudge with rubric-based scoring across three dimensions:
  - research_question_captured: Does the plan reflect the query's research question?
  - purpose_identified: Is the identified purpose aligned with what the query implies?
  - scope: Is the conceptual scope appropriate (not too broad/narrow)?

Usage (standalone):
    python -m evals.artifact.planning_faithfulness samples/case_001/
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

EVAL_NAME = "ae-1"
REQUIRED_ARTIFACTS = ["query", "plan"]

# ---------------------------------------------------------------------------
# Public eval function
# ---------------------------------------------------------------------------

def evaluate_planning_faithfulness(case: CaseData) -> EvalResult:
    """Run the AE-1 planning faithfulness eval on a loaded case.

    Returns an ``EvalResult`` with:
      - score: average of three dimension scores (0.0-1.0)
      - passed: True if score >= 0.7
      - findings: one per dimension explaining the assessment
    """
    judge = LLMJudge()

    prompt = f"""You are evaluating a research planning document produced by an AI research agent.

**User Query:**
{case.query}

**Planning Document (todo.md):**
{case.plan}

Evaluate the plan across three dimensions:

1. **research_question_captured**: Does the plan accurately capture the research question(s) from the user query?
   - "yes": The plan clearly identifies and restates the core research question(s)
   - "partial": The plan captures some aspects but misses or misinterprets key elements
   - "no": The plan does not reflect the user's research question

2. **purpose_identified**: Does the plan identify the correct research purpose implied by the query?
   - "survey": Broad overview across multiple topics/approaches
   - "comparison": Direct comparison between specific approaches/methods
   - "deep_dive": In-depth analysis of a single topic/approach
   - "other": Exploratory or non-standard research purpose
   - "no": No clear purpose identified or purpose is incorrect

3. **scope**: Is the conceptual scope (breadth of research areas) appropriate for the query?
   - "just_right": The plan scopes research areas appropriately for the query
   - "too_broad": The plan attempts to cover more areas than the query requires
   - "too_narrow": The plan misses important areas implied by the query

Anchor examples for scope:
- too_broad: A query asking to compare two specific therapies, but the plan includes general depression mechanisms, historical context, and unrelated treatment modalities
- just_right: A query asking to compare two therapies, and the plan covers mechanisms, evidence, head-to-head comparisons, adherence, and outcomes
- too_narrow: A query asking about effectiveness with multiple outcome dimensions, but the plan only addresses one dimension

Evaluate all three dimensions and provide clear reasoning for your assessment."""

    rubric = {
        "research_question_captured": ["no", "partial", "yes"],
        "purpose_identified": ["no", "survey", "comparison", "deep_dive", "other"],
        "scope": ["too_broad", "too_narrow", "just_right"],
    }

    response = judge.judge_with_rubric(prompt, rubric)

    # Convert rubric values to numeric scores
    rq_score = _score_research_question(response["research_question_captured"])
    purpose_score = _score_purpose(response["purpose_identified"], case.query)
    scope_score = _score_scope(response["scope"])

    overall_score = (rq_score + purpose_score + scope_score) / 3.0
    passed = overall_score >= 0.7

    # Build findings for each dimension
    findings: list[Finding] = []

    # Research question finding
    rq_value = response["research_question_captured"]
    if rq_value == "yes":
        findings.append(Finding(
            severity="info",
            message=f"Research question fully captured ({rq_value})",
            location="research_question_captured",
        ))
    elif rq_value == "partial":
        findings.append(Finding(
            severity="warning",
            message=f"Research question partially captured ({rq_value})",
            location="research_question_captured",
        ))
    else:
        findings.append(Finding(
            severity="error",
            message=f"Research question not captured ({rq_value})",
            location="research_question_captured",
        ))

    # Purpose finding
    purpose_value = response["purpose_identified"]
    if purpose_score >= 1.0:
        findings.append(Finding(
            severity="info",
            message=f"Purpose correctly identified ({purpose_value})",
            location="purpose_identified",
        ))
    else:
        findings.append(Finding(
            severity="error",
            message=f"Purpose not correctly identified ({purpose_value})",
            location="purpose_identified",
        ))

    # Scope finding
    scope_value = response["scope"]
    if scope_value == "just_right":
        findings.append(Finding(
            severity="info",
            message=f"Scope is appropriate ({scope_value})",
            location="scope",
        ))
    elif scope_value == "too_broad":
        findings.append(Finding(
            severity="warning",
            message=f"Scope is too broad ({scope_value})",
            location="scope",
        ))
    else:
        findings.append(Finding(
            severity="warning",
            message=f"Scope is too narrow ({scope_value})",
            location="scope",
        ))

    return EvalResult(
        eval_name=EVAL_NAME,
        score=overall_score,
        max_score=1.0,
        passed=passed,
        findings=findings,
        reasoning=(
            f"{response['reasoning']}\n\n"
            f"Dimension scores: research_question={rq_score:.2f}, "
            f"purpose={purpose_score:.2f}, scope={scope_score:.2f}"
        ),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _score_research_question(value: str) -> float:
    """Convert research question rubric value to score."""
    if value == "yes":
        return 1.0
    elif value == "partial":
        return 0.5
    else:  # "no"
        return 0.0


def _score_purpose(value: str, query: str) -> float:
    """Convert purpose rubric value to score.

    For simplicity, we accept any identified purpose (survey/comparison/deep_dive/other)
    as correct if the LLM identified it. A "no" value indicates the plan lacks a purpose.

    Note: In a production setting, this could use additional logic to validate that
    the identified purpose matches query characteristics (e.g., presence of "vs" or
    "compare" keywords for comparison queries).
    """
    if value in ["survey", "comparison", "deep_dive", "other"]:
        return 1.0
    else:  # "no"
        return 0.0


def _score_scope(value: str) -> float:
    """Convert scope rubric value to score."""
    if value == "just_right":
        return 1.0
    else:  # "too_broad" or "too_narrow"
        return 0.3


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m evals.artifact.planning_faithfulness <case_path>")
        sys.exit(1)

    case = load_case(sys.argv[1])
    result = evaluate_planning_faithfulness(case)
    print(f"AE-1 Planning Faithfulness")
    print(f"  Score:  {result.score:.2f}/{result.max_score}")
    print(f"  Passed: {result.passed}")
    print(f"  Reason: {result.reasoning}")
    if result.findings:
        print(f"  Findings:")
        for f in result.findings:
            print(f"    [{f.severity}] {f.message}")
