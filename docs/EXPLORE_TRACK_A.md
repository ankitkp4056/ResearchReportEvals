# Exploration: Track A — Plan + Structure Evals

**Date:** 2026-04-03  
**Status:** Complete

## Scope Summary

Track A implements three artifact evals that assess whether the generated report follows the research plan and has appropriate depth for the query's stated purpose:

1. **AE-1 Planning Faithfulness** — Does the plan capture research question, purpose, and scope from query?
2. **AE-2 Section Coverage** — Does report address all exploratory areas from plan?
3. **AE-3 Analysis Depth** — Is report depth appropriate for query purpose?

**Key constraint:** These evals require only `query.txt`, `todo.md`, and `report.md` — no dependency on `table.csv` or source papers. This makes Track A independent and parallelizable with Track B.

---

## Existing Infrastructure

### Shared Utilities (Foundation: Complete)

All required utilities already exist and are production-ready:

#### **evals/shared/loader.py**
- `load_case(case_path)` → `CaseData` dataclass
- Loads all four artifacts (query, plan, table, report)
- Returns structured `CaseData` with absolute path to case directory
- Used in: runner, all evals

**Key details:**
- Plan is stored in `CaseData.plan` attribute (read from todo.md)
- Query is stored in `CaseData.query` attribute (read from query.txt)
- Report is stored in `CaseData.report` attribute (read from report.md)
- No need to build custom loaders

#### **evals/shared/llm_judge.py**
- `LLMJudge` class with two main methods:
  - `judge(prompt, response_schema)` — structured JSON output
  - `judge_with_rubric(prompt, rubric)` — forced-choice rubric scoring
- Configuration via environment variables (not hardcoded):
  - `EVAL_LLM_BASE_URL` — endpoint URL
  - `EVAL_LLM_API_KEY` — API key
  - `EVAL_LLM_MODEL` — model name
- Handles JSON parse failures with retry logic (up to 3 attempts)
- Automatically strips markdown fences from LLM response

**Key usage pattern for Track A:**
```python
from evals.shared.llm_judge import LLMJudge
judge = LLMJudge()
result = judge.judge_with_rubric(prompt, rubric_dict)
# Returns dict mapping dimension -> value, always includes "reasoning" key
```

#### **evals/shared/results.py**
- `Finding` dataclass: severity (error/warning/info), message, optional location
- `EvalResult` dataclass: eval_name, score, max_score, passed, findings[], reasoning
- `CaseResults` class: aggregates multiple `EvalResult` objects, handles JSON serialization
- Convenience methods: `passed_count()`, `total_score()`, `total_max_score()`

**Key pattern:**
```python
result = EvalResult(
    eval_name="ae-1",
    score=0.75,
    max_score=1.0,
    passed=(0.75 >= 0.7),  # threshold logic
    findings=[Finding(severity="warning", message="...", location="...")],
    reasoning="Explanation from LLM or script"
)
```

#### **evals/shared/citation_parser.py**
- Not needed for Track A (no citation extraction required)
- Included here for reference (used by Track B and AE-6)

#### **evals/shared/claim_extractor.py**
- Not needed for Track A (no claim extraction required)
- Uses `LLMJudge` internally for claim identification
- Included here for reference (used by Track B)

### Eval Runner & Registry (Foundation: Complete)

**evals/run.py** provides the registration and execution framework:

#### **Registry Pattern**
```python
EVAL_REGISTRY: dict[str, dict]  # Global registry
register_eval(name: str, fn: Callable, required_artifacts: list[str])
```

Track A evals must:
1. Define module-level constants:
   - `EVAL_NAME = "ae-1"` (must be unique across all evals)
   - `REQUIRED_ARTIFACTS = ["query", "plan"]` (attribute names on CaseData)
2. Implement `evaluate_X(case: CaseData) -> EvalResult` function
3. Call `register_eval()` at module import time OR import happens in `evals/run.py`

**Artifact name mapping** (in runner):
```python
_ARTIFACT_ATTR_MAP = {
    "report": "report",
    "table": "table",
    "plan": "plan",
    "query": "query",
}
```

Track A must use: `"query"`, `"plan"`, `"report"` (not `"table"`).

#### **Standalone Execution**
Each eval is runnable as:
```bash
python -m evals.artifact.planning_faithfulness samples/case_001/
```

This requires a `if __name__ == "__main__"` block. See `fabricated_references.py` for the exact pattern.

### Existing Eval: AE-6 Fabricated References

**evals/artifact/fabricated_references.py** is an excellent pattern-matching reference:

```python
EVAL_NAME = "ae-6"
REQUIRED_ARTIFACTS = ["report", "table"]

def evaluate_fabricated_references(case: CaseData) -> EvalResult:
    # 1. Extract data
    body = _strip_references_section(case.report)
    citations = extract_citations(body)
    table = case.table
    
    # 2. Compute findings
    findings = [...]  # list of Finding objects
    
    # 3. Compute score
    score = 1.0 if not findings else 0.0
    passed = len(findings) == 0
    
    # 4. Return EvalResult
    return EvalResult(
        eval_name=EVAL_NAME,
        score=score,
        max_score=1.0,
        passed=passed,
        findings=findings,
        reasoning=f"..."
    )

# 5. Standalone entry point
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: ...")
        sys.exit(1)
    case = load_case(sys.argv[1])
    result = evaluate_fabricated_references(case)
    # Print result
```

---

## Sample Test Data

**samples/case_001/** contains all artifacts:

- `query.txt` (139 bytes): "Compare effectiveness of CBT vs DBT for treatment-resistant depression, focusing on remission rates, dropout rates, and long-term outcomes"
- `todo.md` (2,723 bytes): Structured plan with 7 sections (Background, CBT mechanisms, DBT mechanisms, Head-to-head comparisons, Dropout/adherence, Long-term outcomes, Limitations)
- `report.md` (7,636 bytes): Generated report with 7 sections matching plan, plus intentional defects (fabricated reference, uncited claims, citation mismatch)
- `table.csv` (1,724 bytes): Extraction table (not used by Track A)

**Plan structure in todo.md:**
```markdown
# Research Plan: [Title]
**Query:** [copy of query]
**Purpose:** [one of: Comparative survey, Survey, Deep-dive, Other]
---
## Research Areas
### 1. Background: [Title]
### 2. [Topic]: [Title]
...
## Search Strategy
...
## Deliverable
...
```

**Report structure in report.md:**
```markdown
# [Title]
## Introduction
## [Section 1]
## [Section 2]
...
## References
```

---

## Key Decisions & Patterns

### 1. LLM Judge as Primary Tool for All Three Evals

All three Track A evals are **LLM-judge** evals, not script-only. They require the `LLMJudge` class to score or classify aspects.

**Why:** Deterministic script approaches (e.g., regex headings) are error-prone. LLM judgment is more robust and can handle varied markdown formats, phrasing, and implicit vs. explicit structure.

### 2. Rubric-Based Scoring for Consistency

Use `judge_with_rubric()` for all scoring. Define dimensions explicitly and provide allowed values.

**Example for AE-1 (Planning Faithfulness):**
```python
rubric = {
    "research_question": ["no", "partial", "yes"],
    "purpose_identified": ["no", "survey", "comparison", "deep-dive", "other"],
    "scope": ["too_broad", "just_right", "too_narrow"],
}
```

This forces the LLM to pick from your allowed values, reducing parsing errors.

### 3. Findings List for Explanation

Always populate `findings[]` even for LLM-based evals. Use it to explain **what** the rubric dimensions scored and **why**.

Example:
```python
findings = [
    Finding(
        severity="warning",
        message="Research question only partially captured in plan",
        location="## Research Areas (section title)"
    ),
    Finding(
        severity="info",
        message="Purpose identified as comparative survey — matches query intent",
        location="**Purpose:** line"
    ),
]
```

### 4. Scoring Aggregation

For multi-dimension rubrics, aggregate by averaging:
```python
# Convert rubric values to scores
scores = {
    "research_question": {"yes": 1.0, "partial": 0.5, "no": 0.0}[result["research_question"]],
    "purpose": 1.0,  # or 0.0 depending on logic
    "scope": {"just_right": 1.0, "too_broad": 0.3, "too_narrow": 0.3}[result["scope"]],
}
overall_score = sum(scores.values()) / len(scores)
```

### 5. Passing Threshold Logic

Define clear thresholds for `passed` boolean:
- **AE-1:** passed if overall_score >= 0.7 (typically "mostly right")
- **AE-2:** passed if coverage >= 0.75 (75% of plan areas addressed)
- **AE-3:** passed if depth_score >= 0.6 (moderate depth for purpose)

---

## Integration Points & Dependencies

### Immediate Dependencies

1. **evals/run.py** — must import Track A evals and register them
2. **Environment variables** — must be set before calling LLMJudge:
   - `EVAL_LLM_BASE_URL`, `EVAL_LLM_API_KEY`, `EVAL_LLM_MODEL`
3. **OpenAI SDK** — already in requirements.txt, used by LLMJudge

### Loose Coupling

Track A does **not** depend on:
- Table parser (Track B and AE-6 do)
- Citation parser (Track B and AE-6 do)
- Claim extractor (Track B does)
- Source papers (Track B does)

This independence is deliberate and allows parallel implementation with Track B.

---

## Design Decisions Resolved

### 1. Markdown Heading Extraction for AE-2

**Decision:** Use LLM to extract headings + understand hierarchy, not regex.

**Rationale:** 
- Markdown heading levels can vary (# vs ##, inconsistent nesting)
- Some reports may use bold text instead of headings
- LLM can infer "sections" from content structure even without formal headings
- More robust to malformed markdown

**Alternative rejected:** Regex-based extraction — fragile, requires manual markdown cleanup.

### 2. Single-Pass LLM Call vs. Multi-Pass for AE-2

**Decision:** Single LLM call per eval; provide plan + report together in one prompt.

**Rationale:**
- Reduces API calls and latency
- LLM can reason over both artifacts in one pass
- Simpler error handling and result parsing

**Alternative rejected:** Multi-pass (extract plan sections → extract report sections → map); more complex, no benefit.

### 3. Depth Scoring for AE-3

**Decision:** First classify query purpose with LLM, then apply purpose-specific rubric.

**Rationale:**
- Query purpose directly determines what "appropriate depth" means
- A survey should be broad + brief; a deep-dive should be narrow + detailed
- Two-step approach (classify → score) is clearer than one-step joint scoring

**Alternative rejected:** Blind depth scoring without purpose context; too ambiguous.

---

## Edge Cases & Risks Identified

### AE-1: Planning Faithfulness

**Edge case 1:** Multiple research questions in query?
- Query might have OR structure: "Compare X vs Y to either improve Z or understand W"
- **Mitigation:** LLM rubric asks: "Does plan capture *the main* research question(s)?" — allow partial credit if subset captured

**Edge case 2:** Plan with no explicit "Purpose" line?
- Some agents may not have a `**Purpose:**` field
- **Mitigation:** LLM should infer purpose from plan content (e.g., section structure, tone), not just look for a keyword

**Risk:** LLM may misclassify vague queries or overly broad plans as "correct"
- **Mitigation:** Spot-check results; calibrate rubric with 5-10 manual annotations

### AE-2: Section Coverage

**Edge case 1:** Plan with nested sections vs. report with flat sections?
- Plan might have 7 main sections with sub-bullets
- Report might have 10 sections, some combining plan topics
- **Mitigation:** LLM should map at the topic level, not strict heading level
- **Prompt guidance:** "Map plan topics (even if nested) to report sections even if reorganized"

**Edge case 2:** Report adds sections not in plan (e.g., "Limitations", "Future Research")?
- Should not penalize for extra content
- **Mitigation:** Scoring formula: `covered_topics / plan_topics` (not considering report-only sections)

**Edge case 3:** Report sections are vague or implicit?
- Some reports may not have clear headings; structure implied
- **Mitigation:** Ask LLM to infer sections from content ("even if not explicitly headed")

**Risk:** Overcounting "partial coverage" (too lenient) or undercounting (too strict)
- **Mitigation:** Manual spot-check; gather 5-10 cases with gold annotations

### AE-3: Analysis Depth

**Edge case 1:** Query purpose is ambiguous?
- Query might read as survey but also have comparison elements
- **Mitigation:** LLM classification should return primary + secondary purpose with confidence
- **Fallback:** If ambiguous, default to "survey" (more permissive on breadth)

**Edge case 2:** Report depth doesn't match purpose but report is still good?
- e.g., survey query answered with 3-paper deep-dive (narrow but high quality)
- **Mitigation:** This is a legitimate "fail" case for AE-3 (misalignment), even if report quality is high
- Design is correct; don't over-engineer

**Edge case 3:** No clear purpose in query?
- Some queries might be exploratory or open-ended
- **Mitigation:** LLM rubric should allow "exploratory" as a purpose category
- Score depth neutrally if purpose is truly undefined

**Risk:** LLM depth judgment is subjective (what is "sufficient" detail?)
- **Mitigation:** Provide rubric with concrete criteria per purpose:
  - Survey → minimum 5 papers, at least 3 distinct research areas mentioned
  - Comparison → at least 2 explicit comparisons, >3 dimensions compared
  - Deep-dive → >1,000 words per paper, methodology discussion, limitations

---

## Ambiguities & Open Questions

### Q1: What is the exact scoring scale for AE-2 Section Coverage?

**Current spec:** "Coverage percentage + findings listing missing/underexplored areas"

**Ambiguity:** How to count "partial coverage"?
- Option A: Fully covered = 1.0, partially = 0.5, missing = 0.0 per topic → average
- Option B: Fully covered = 1.0, partially = 0.7, missing = 0.0 per topic → average
- Option C: Use LLM to estimate % coverage per topic (0-100%), then average

**Recommendation:** Use Option A (simplest); LLM assigns one of {full, partial, missing} per topic.

### Q2: What are concrete "too broad" vs "just right" vs "too narrow" scopes for AE-1?

**Current spec:** Rubric has three options but no definition

**Ambiguity:** What makes a scope "too broad" for a TRD comparison query?
- Too broad: "Study all psychotherapy for depression" (loses focus on CBT/DBT)
- Too narrow: "Compare CBT vs DBT session-by-session for one patient" (n=1)
- Just right: "Compare CBT vs DBT for TRD on remission/dropout/long-term outcomes"

**Recommendation:** Include scope examples in the LLM prompt as anchors:
```
Scope guide:
- Too broad: Wider than the query scope (e.g., includes unrelated therapies)
- Just right: Directly matches query scope and focus areas
- Too narrow: Excludes important aspects mentioned in query
```

### Q3: Should AE-3 penalize if query is "survey" but report is "deep-dive"?

**Current spec:** "Is depth appropriate for query purpose?"

**Ambiguity:** "Appropriate" might mean:
- Option A: Matching (report depth ≈ query purpose) — strict
- Option B: Adequate (report depth >= query purpose minimum) — lenient

**Recommendation:** Use strict interpretation (Option A). If query asks for survey, a deep-dive is misaligned. A future eval can measure "report quality" separately.

### Q4: For AE-2, should we count "Introduction" and "Conclusion" as plan-required sections?

**Current spec:** "extract section headings from todo.md" and match to report

**Ambiguity:** 
- Plan typically has: Background, Evidence Base, Comparisons, Dropout, Long-term outcomes, Limitations, etc.
- Report typically has: Introduction, Sections matching plan, Discussion, Limitations, Conclusion, References
- Should Introduction/Conclusion be considered "coverage" of plan areas?

**Recommendation:** No. Only match sections that directly address plan research areas. Introduction and Conclusion are structural, not content areas.

### Q5: What if todo.md has sections but report doesn't reference them clearly?

**Ambiguity:** Plan says "### 5. Dropout and Adherence" but report discusses dropout inline without a heading

**Recommendation:** LLM should infer from content ("even if not explicitly headed"). Prompt should say:
```
Map each plan research area to corresponding report content.
Report sections may be reorganized, combined, or written inline.
Look for topic coverage in the content, not just heading matches.
```

### Q6: Should AE-1 validate the "Search Strategy" section of the plan?

**Current spec:** Focus on research question, purpose, and scope

**Ambiguity:** "Scope" could mean:
- Conceptual scope: How narrow/broad are the research areas?
- Practical scope: Are search strategies defined? Date ranges set? Database selection made?

**Recommendation:** Focus on conceptual scope (research areas), not search strategy. Search strategy is a Step 2 eval (not in Track A scope).

---

## File Paths & Locations

**Key files to be created or modified:**

1. `/tmp/sra-track-a/evals/artifact/planning_faithfulness.py` — AE-1 (new)
2. `/tmp/sra-track-a/evals/artifact/section_coverage.py` — AE-2 (new)
3. `/tmp/sra-track-a/evals/artifact/analysis_depth.py` — AE-3 (new)
4. `/tmp/sra-track-a/evals/run.py` — register Track A evals (modify)
5. `/tmp/sra-track-a/tests/test_planning_faithfulness.py` — unit tests (new, optional)
6. `/tmp/sra-track-a/tests/test_section_coverage.py` — unit tests (new, optional)
7. `/tmp/sra-track-a/tests/test_analysis_depth.py` — unit tests (new, optional)

**Test data:**
- `/tmp/sra-track-a/samples/case_001/` — all artifacts present and ready

**Documentation:**
- `/tmp/sra-track-a/docs/SPRINT_TRACK_A.md` — existing sprint spec (read-only)

---

## Implementation Notes

### Imports Pattern

Each eval module should import:
```python
from evals.shared.loader import CaseData, load_case
from evals.shared.llm_judge import LLMJudge
from evals.shared.results import EvalResult, Finding
```

### LLMJudge Initialization

In each eval function:
```python
def evaluate_planning_faithfulness(case: CaseData) -> EvalResult:
    judge = LLMJudge()  # Reads env vars on init
    # Use judge.judge_with_rubric(...) or judge.judge(...)
```

**Do NOT** cache `LLMJudge()` at module level; it fails if env vars are not set at import time.

### Rubric Keys

Rubric dict keys become JSON keys in the LLM response. Use snake_case for consistency:
```python
rubric = {
    "research_question_captured": ["no", "partial", "yes"],
    "purpose_identified": ["survey", "comparison", "deep_dive", "other"],
}
```

### Reasoning Field

Always include comprehensive reasoning that explains the score and any trade-offs:
```python
reasoning = (
    f"Plan captures research question (score: {rq_score}). "
    f"Purpose identified as '{result['purpose_identified']}' (score: {purpose_score}). "
    f"Scope deemed '{result['scope']}' (score: {scope_score}). "
    f"Overall: {overall_score}/1.0"
)
```

---

## Implementation Checklist

Before starting implementation:

- [ ] All env vars (`EVAL_LLM_BASE_URL`, `EVAL_LLM_API_KEY`, `EVAL_LLM_MODEL`) documented for user
- [ ] Standalone entry points (`if __name__ == "__main__"`) required per spec
- [ ] Each eval registers via `register_eval()` in `evals/run.py`
- [ ] Test data in `samples/case_001/` confirmed valid and complete
- [ ] Type hints on all functions (encouraged by spec)
- [ ] `EvalResult` fields match spec (score 0-1, max_score=1.0, passed=bool, findings=[], reasoning=str)

---

## Summary

Track A is well-positioned for implementation. The infrastructure is solid:

- **Shared utilities:** Complete and production-ready (loader, LLMJudge, results schema)
- **Eval runner:** Registry pattern established and working (demonstrated by AE-6)
- **Sample data:** Complete test case with realistic artifacts and intentional defects
- **Documentation:** Clear sprint spec, eval strategy, and established patterns

**Key constraints:**
- No table.csv or source papers required (clean independence)
- LLM-judge based (requires OpenAI-compatible endpoint)
- Rubric-driven scoring (explicit dimensions, forced choices)

**Next steps (to be clarified with user):**
1. Confirm scoring thresholds and aggregation logic for each eval (especially AE-2)
2. Clarify scope definition bounds for AE-1 (with examples)
3. Decide strict vs. lenient interpretation for AE-3 mismatch cases
4. Determine passing thresholds for each eval

All foundation is ready for rapid implementation once decisions are finalized.
