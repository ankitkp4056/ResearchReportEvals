# Feature Implementation Plan

**Overall Progress:** `100%`

## TLDR

Wire all foundation modules into a working eval pipeline: populate package init files with proper exports, build a registry-based eval runner with CLI, implement the AE-6 fabricated references eval as the first end-to-end integration, add missing dependencies, and validate the full flow against sample data.

## Exploration Summary

**Existing modules (all complete in `evals/shared/`):**
- `loader.py` -- `CaseData` dataclass and `load_case()` function; loads `query.txt`, `todo.md`, `table.csv`, `report.md` from a case directory.
- `citation_parser.py` -- `Citation` dataclass, `extract_citations()` (supports parenthetical, bracket, narrative author-year, and numeric `[N]` formats), `match_citation_to_table()` (author-year matching only; returns `None` for numeric refs).
- `table_parser.py` -- `PaperRecord` dataclass, `parse_table()`, `get_paper_by_title()` (fuzzy match via `difflib.SequenceMatcher`).
- `results.py` -- `Finding`, `EvalResult`, `CaseResults` dataclasses with JSON serialization (`save`/`load` on `CaseResults`).
- `llm_judge.py` -- `LLMJudge` class wrapping OpenAI-compatible chat completions with retry and JSON parsing.
- `claim_extractor.py` -- `Claim` dataclass, `extract_claims()` using `LLMJudge`.

**Package init files:** All four (`evals/`, `evals/shared/`, `evals/artifact/`, `evals/system/`) are one-line comment stubs with no exports.

**Sample data (`samples/case_001/`):** Report contains 30 numeric citations `[1]`--`[30]`. Table has 30 papers in the first 30 rows (98 total rows). Reference `[6]` (Tanaka et al.) appears in the References section but is never cited in the body -- this is the planted fabricated reference, but it will not be caught by the current AE-6 design (which checks inline citations against the table, not unused references).

**requirements.txt:** Has `openai>=1.0.0` and `pytest>=7.0.0`. Missing `rapidfuzz>=3.0.0`.

**Key constraint:** `match_citation_to_table()` returns `None` for numeric citations (no author/year to match). AE-6 must handle numeric refs by mapping `[N]` to table row index `N-1`.

## Critical Decisions

- Decision 1: Numeric citation matching via table row index -- For numeric refs like `[N]`, map to table row `N-1` since `match_citation_to_table()` cannot resolve them structurally. This assumes table rows are ordered to match the reference numbering.
- Decision 2: Use raw `CaseData.table` (list[dict]) for AE-6 matching -- Avoids the stricter validation of `parse_table()` and keeps the eval simple since it only needs row-level existence checks.
- Decision 3: Registry pattern for eval runner -- Dict mapping eval name to function + required artifacts list. Runner checks artifact availability before executing each eval.
- Decision 4: Per-eval error isolation -- Runner catches exceptions from individual evals, logs them, and continues with remaining evals so one failure does not block others.
- Decision 5: AE-6 expected result on sample data -- All 30 inline citations match the table, so AE-6 returns `score=1.0, passed=True`. The planted fabricated reference (unused `[6]` in References section) is a target for a future "unused references" eval, not AE-6.

## Tasks

- [ ] **Step 1: Package init files**
  - [ ] 🟥 `evals/__init__.py` -- leave as minimal package marker (no exports needed at top level)
  - [ ] 🟥 `evals/shared/__init__.py` -- add imports and `__all__` exporting: `CaseData`, `LLMJudge`, `EvalResult`, `CaseResults`, `Citation`, `Claim`, `PaperRecord`, `Finding`
  - [ ] 🟥 `evals/artifact/__init__.py` -- leave as minimal package marker
  - [ ] 🟥 `evals/system/__init__.py` -- leave as minimal package marker

- [ ] **Step 2: AE-6 fabricated references eval** (`evals/artifact/fabricated_references.py`)
  - [ ] 🟥 Create `evaluate_fabricated_references(case: CaseData) -> EvalResult` function
  - [ ] 🟥 Step 1: call `extract_citations(case.report)` to get all inline citations
  - [ ] 🟥 Step 2: for each citation, attempt matching -- for author-year citations use `match_citation_to_table(citation, case.table)`, for numeric refs `[N]` check that table row index `N-1` exists (i.e., `int(citation.reference_id) <= len(case.table)`)
  - [ ] 🟥 Step 3: collect unmatched citations as `Finding(severity="error", message=..., location=citation.raw_text)`
  - [ ] 🟥 Step 4: return `EvalResult(eval_name="ae-6", score=1.0 if no findings else 0.0, max_score=1.0, passed=..., findings=..., reasoning=...)`
  - [ ] 🟥 Add standalone `__main__` block: `python -m evals.artifact.fabricated_references samples/case_001/`
  - [ ] 🟥 Register eval name "ae-6" with required artifacts `["report", "table"]`

- [ ] **Step 3: Eval runner and CLI** (`evals/run.py`)
  - [ ] 🟥 Define `EVAL_REGISTRY` dict -- keys are eval names (e.g., `"ae-6"`), values are dicts with `"fn"` (callable taking `CaseData`, returning `EvalResult`) and `"required_artifacts"` (list of strings like `["report", "table"]`)
  - [ ] 🟥 Import and register AE-6: `from evals.artifact.fabricated_references import evaluate_fabricated_references`
  - [ ] 🟥 Implement `_has_artifacts(case: CaseData, required: list[str]) -> bool` -- checks that the required artifact fields on `CaseData` are non-empty (e.g., `"report"` checks `case.report`, `"table"` checks `case.table`)
  - [ ] 🟥 Implement `run_evals(case_path: str, only: list[str] | None = None) -> CaseResults` -- calls `load_case()`, filters registry by `--only` flag if provided, checks artifact availability, runs each eval in a try/except, collects results into `CaseResults`
  - [ ] 🟥 Implement summary printer -- prints a table to stdout with columns: eval name, score, max_score, passed, finding count
  - [ ] 🟥 Implement `main()` with argparse -- positional `case_path` arg, optional `--only` flag (comma-separated eval names), calls `run_evals()`, prints summary, calls `CaseResults.save(case_path)`
  - [ ] 🟥 Add `if __name__ == "__main__"` block calling `main()`

- [ ] **Step 4: Update requirements.txt**
  - [ ] 🟥 Add `rapidfuzz>=3.0.0` to `requirements.txt` (keep existing `openai>=1.0.0` and `pytest>=7.0.0`)

- [ ] **Step 5: End-to-end validation**
  - [ ] 🟥 Run `python -m evals.run samples/case_001/` -- confirm AE-6 executes without errors
  - [ ] 🟥 Verify `samples/case_001/eval_results.json` is created with correct JSON structure (array of EvalResult dicts)
  - [ ] 🟥 Verify AE-6 result: `score=1.0`, `passed=True`, empty findings list (all 30 numeric citations match table rows)
  - [ ] 🟥 Run `python -m evals.run samples/case_001/ --only ae-6` -- confirm selective execution works
