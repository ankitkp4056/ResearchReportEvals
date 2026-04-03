# Sprint: Foundation — Integration

**Overall Progress:** `100%`

## TLDR
Wire everything together: eval runner/CLI, AE-6 (first eval + integration test), requirements.txt, and package init files. This session runs AFTER the Parsers and LLM sessions complete.

## Prerequisites
- `SPRINT_FOUNDATION_PARSERS.md` must be complete — provides: `evals/shared/loader.py`, `evals/shared/citation_parser.py`, `evals/shared/table_parser.py`, sample data in `samples/case_001/`
- `SPRINT_FOUNDATION_LLM.md` must be complete — provides: `evals/shared/llm_judge.py`, `evals/shared/claim_extractor.py`, `evals/shared/results.py`

## Context
- Eval strategy: `docs/EVAL_STRATEGY.md`
- Python 3.11+, type hints encouraged
- AE-6 goes in `evals/artifact/fabricated_references.py`
- Each eval must be runnable standalone: `python -m evals.artifact.fabricated_references samples/case_001/`
- AE-6 is a pure script eval (no LLM needed) — it validates the parsers work end-to-end

## Tasks

- [x] :white_check_mark: **Task 1: Package init files**
  - [x] :white_check_mark: Create `evals/__init__.py`
  - [x] :white_check_mark: Create `evals/shared/__init__.py` — export key classes: `CaseData`, `LLMJudge`, `EvalResult`, `CaseResults`, `Citation`, `Claim`, `PaperRecord`
  - [x] :white_check_mark: Create `evals/artifact/__init__.py`
  - [x] :white_check_mark: Create `evals/system/__init__.py`

- [x] :white_check_mark: **Task 2: Eval runner + CLI** (`evals/run.py`)
  - [x] :white_check_mark: Eval registry: each eval registers itself with a name and list of required artifacts (e.g., `["report", "table"]`)
  - [x] :white_check_mark: Runner: load case via `load_case()`, discover applicable evals (check required artifacts exist), run all, aggregate into `CaseResults`
  - [x] :white_check_mark: CLI: `python -m evals.run samples/case_001/` — runs all evals, prints summary table to terminal, writes `eval_results.json` to case folder
  - [x] :white_check_mark: Selective run: `--only ae-6,ae-1` flag to run subset of evals
  - [x] :white_check_mark: Error handling: if one eval fails, log error and continue with remaining evals

- [x] :white_check_mark: **Task 3: AE-6 — Fabricated References** (`evals/artifact/fabricated_references.py`)
  - [x] :white_check_mark: Load case using artifact loader
  - [x] :white_check_mark: Extract all citations from report using `extract_citations()`
  - [x] :white_check_mark: Extract paper list from table using `parse_table()` or raw `CaseData.table`
  - [x] :white_check_mark: Cross-match: for each citation, attempt to match against table using `match_citation_to_table()`. Flag unmatched citations as fabricated
  - [x] :white_check_mark: Return `EvalResult` with: score=1.0 if no fabricated refs else 0.0, findings listing each fabricated ref as severity="error"
  - [x] :white_check_mark: Register with eval runner
  - [x] :white_check_mark: Test against `samples/case_001/` — AE-6 passes (score=1.0): all 16 body citations resolve to table rows. Note: the planted reference [6] is in the References list but never cited in body text — it's an "unused reference" issue, not a fabricated citation.

- [x] :white_check_mark: **Task 4: requirements.txt**
  - [x] :white_check_mark: Add dependencies: `openai` (for LLM client), `rapidfuzz` (for fuzzy matching in citation/table parser)
  - [x] :white_check_mark: Pin versions

- [x] :white_check_mark: **Task 5: End-to-end validation**
  - [x] :white_check_mark: Run `python -m evals.run samples/case_001/` — AE-6 executes successfully
  - [x] :white_check_mark: Verify `samples/case_001/eval_results.json` is created with correct structure
  - [x] :white_check_mark: AE-6 result: score=1.0, passed=True, 0 findings — 16 body citations checked against 98 table rows, all matched
