# Feature Implementation Plan

**Overall Progress:** `100%`

## TLDR

Build three LLM-judge artifact evals (AE-1 Planning Faithfulness, AE-2 Section Coverage, AE-3 Analysis Depth) that assess whether the generated report follows the research plan. These evals depend only on query.txt, todo.md, and report.md -- no table or source paper dependencies. Each eval uses the shared LLMJudge with rubric-based scoring, returns EvalResult, registers with the eval runner, and is runnable standalone.

## Exploration Summary

**Infrastructure (all complete and ready):**
- `evals/shared/loader.py` -- `load_case()` returns `CaseData` with `.query`, `.plan`, `.report`, `.table` attributes
- `evals/shared/llm_judge.py` -- `LLMJudge` class reads env vars (`EVAL_LLM_BASE_URL`, `EVAL_LLM_API_KEY`, `EVAL_LLM_MODEL`) at init; provides `judge(prompt, response_schema)` and `judge_with_rubric(prompt, rubric)` methods; rubric method validates dimensions and always returns a `"reasoning"` key
- `evals/shared/results.py` -- `Finding(severity, message, location)`, `EvalResult(eval_name, score, max_score, passed, findings, reasoning)`
- `evals/run.py` -- `register_eval(name, fn, required_artifacts)` pattern; `_ARTIFACT_ATTR_MAP` maps "query", "plan", "report", "table" to CaseData attributes
- `evals/artifact/fabricated_references.py` -- AE-6 reference implementation showing exact module pattern (constants, eval function, standalone `__main__` block)

**Sample data (`samples/case_001/`):**
- `query.txt`: CBT vs DBT comparison query (139 bytes)
- `todo.md`: 7-section plan with `**Purpose:** Comparative survey` line (2,723 bytes)
- `report.md`: 7-section report with intentional defects (7,636 bytes)

**Key patterns from exploration:**
- Do NOT cache `LLMJudge()` at module level; instantiate inside the eval function
- Rubric keys use snake_case; values are lists of allowed strings (worst-to-best)
- Each module defines `EVAL_NAME`, `REQUIRED_ARTIFACTS`, and the evaluate function
- `judge_with_rubric()` returns a dict with dimension keys + `"reasoning"` key; validates all values against allowed options

**Edge cases identified:**
- AE-1: Plans may lack explicit `**Purpose:**` line; LLM should infer from content
- AE-1: Queries may contain multiple research questions; allow partial credit
- AE-2: Report sections may be reorganized, combined, or lack explicit headings; LLM must match by topic content not heading text
- AE-2: Extra report sections (Limitations, Future Research) should not penalize
- AE-3: Ambiguous query purpose; LLM classification should handle "exploratory" as a category
- AE-3: Depth mismatch (survey query answered with deep-dive) is a legitimate fail

## Critical Decisions

- Decision 1: Use `judge_with_rubric()` for all three evals -- forces the LLM into fixed dimension values, reducing parse errors and ensuring consistent scoring
- Decision 2: Single LLM call per eval (provide both artifacts in one prompt) -- reduces latency and simplifies error handling vs multi-pass approach
- Decision 3: AE-2 uses simple three-level coverage (full=1.0, partial=0.5, missing=0.0) per topic then averages -- simplest option, avoids over-engineering
- Decision 4: AE-3 uses two-step approach (classify purpose, then apply purpose-specific rubric) via a single `judge()` call with structured schema -- purpose context determines what "appropriate depth" means
- Decision 5: Passing thresholds: AE-1 >= 0.7, AE-2 >= 0.75, AE-3 >= 0.6 -- calibrated to "mostly right" expectations
- Decision 6: Scope in AE-1 focuses on conceptual scope (research areas) not search strategy -- search strategy is a Step 2 eval outside Track A

## Tasks

- [x] **Step 1: AE-1 Planning Faithfulness (`evals/artifact/planning_faithfulness.py`)**
  - [x] Create module with `EVAL_NAME = "ae-1"` and `REQUIRED_ARTIFACTS = ["query", "plan"]`
  - [x] Build LLM prompt that provides the user query and plan text, asking the judge to evaluate three dimensions: research question captured, purpose identified, scope appropriateness. Include scope anchor examples (too broad / just right / too narrow) in the prompt
  - [x] Define rubric dict: `research_question_captured` -> [no, partial, yes], `purpose_identified` -> [no, survey, comparison, deep_dive, other], `scope` -> [too_broad, just_right, too_narrow]
  - [x] Implement `evaluate_planning_faithfulness(case: CaseData) -> EvalResult`: instantiate LLMJudge, call `judge_with_rubric()`, convert rubric values to numeric scores (research_question: yes=1.0/partial=0.5/no=0.0; purpose: correct match=1.0/wrong or missing=0.0; scope: just_right=1.0/too_broad=0.3/too_narrow=0.3), average for overall score, populate findings from each dimension, set passed = score >= 0.7
  - [x] Add standalone `if __name__ == "__main__"` block matching AE-6 pattern (load case from sys.argv[1], print score/passed/reasoning/findings)
  - [x] Verify standalone execution against `samples/case_001/`

- [x] **Step 2: AE-2 Section Coverage (`evals/artifact/section_coverage.py`)**
  - [x] Create module with `EVAL_NAME = "ae-2"` and `REQUIRED_ARTIFACTS = ["plan", "report"]`
  - [x] Build LLM prompt that provides the full plan and full report, asking the judge to: (1) identify all research topic areas from the plan, (2) for each topic area determine coverage status in the report (full / partial / missing), with guidance that report sections may be reorganized or combined and to match by content not headings
  - [x] Use `judge()` (not `judge_with_rubric`) with a response schema requesting: `topics` (list of objects with `topic_name`, `coverage` one of full/partial/missing, `report_location`), and `reasoning`
  - [x] Implement `evaluate_section_coverage(case: CaseData) -> EvalResult`: instantiate LLMJudge, call `judge()`, compute coverage score (full=1.0 + partial=0.5 + missing=0.0 divided by total topics), create Finding per topic (info for full, warning for partial, error for missing), set passed = score >= 0.75
  - [x] Add standalone `if __name__ == "__main__"` block matching AE-6 pattern
  - [x] Verify standalone execution against `samples/case_001/`

- [x] **Step 3: AE-3 Analysis Depth (`evals/artifact/analysis_depth.py`)**
  - [x] Create module with `EVAL_NAME = "ae-3"` and `REQUIRED_ARTIFACTS = ["query", "report"]`
  - [x] Build LLM prompt that provides the user query and full report, asking the judge to: (1) classify the query purpose (survey / comparison / deep_dive / exploratory), (2) based on classified purpose apply purpose-specific criteria (survey: breadth of topics, paper count, conciseness; comparison: cross-paper analysis, dimensions compared, synthesis; deep_dive: depth per paper, methodology, limitations), (3) score depth on 1-5 scale
  - [x] Use `judge()` with a response schema requesting: `purpose` (string), `depth_score` (integer 1-5), `purpose_criteria_met` (list of strings), `purpose_criteria_missed` (list of strings), `reasoning`
  - [x] Implement `evaluate_analysis_depth(case: CaseData) -> EvalResult`: instantiate LLMJudge, call `judge()`, normalize depth_score to 0-1 range ((score-1)/4), create findings from criteria met/missed, set passed = normalized score >= 0.6
  - [x] Add standalone `if __name__ == "__main__"` block matching AE-6 pattern
  - [x] Verify standalone execution against `samples/case_001/`

- [x] **Step 4: Register Track A evals in eval runner (`evals/run.py`)**
  - [x] Add import block for AE-1: import `EVAL_NAME`, `REQUIRED_ARTIFACTS`, `evaluate_planning_faithfulness` from `evals.artifact.planning_faithfulness`; call `register_eval()`
  - [x] Add import block for AE-2: import from `evals.artifact.section_coverage`; call `register_eval()`
  - [x] Add import block for AE-3: import from `evals.artifact.analysis_depth`; call `register_eval()`
  - [x] Verify runner can execute Track A evals: `python -m evals.run samples/case_001/ --only ae-1,ae-2,ae-3`
