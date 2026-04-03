# Sprint: Foundation — Integration

**Overall Progress:** `0%`

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

- [ ] 🟥 **Task 1: Package init files**
  - [ ] 🟥 Create `evals/__init__.py`
  - [ ] 🟥 Create `evals/shared/__init__.py` — export key classes: `CaseData`, `LLMJudge`, `EvalResult`, `CaseResults`, `Citation`, `Claim`, `PaperRecord`
  - [ ] 🟥 Create `evals/artifact/__init__.py`
  - [ ] 🟥 Create `evals/system/__init__.py`

- [ ] 🟥 **Task 2: Eval runner + CLI** (`evals/run.py`)
  - [ ] 🟥 Eval registry: each eval registers itself with a name and list of required artifacts (e.g., `["report", "table"]`)
  - [ ] 🟥 Runner: load case via `load_case()`, discover applicable evals (check required artifacts exist), run all, aggregate into `CaseResults`
  - [ ] 🟥 CLI: `python -m evals.run samples/case_001/` — runs all evals, prints summary table to terminal, writes `eval_results.json` to case folder
  - [ ] 🟥 Selective run: `--only ae-6,ae-1` flag to run subset of evals
  - [ ] 🟥 Error handling: if one eval fails, log error and continue with remaining evals

- [ ] 🟥 **Task 3: AE-6 — Fabricated References** (`evals/artifact/fabricated_references.py`)
  - [ ] 🟥 Load case using artifact loader
  - [ ] 🟥 Extract all citations from report using `extract_citations()`
  - [ ] 🟥 Extract paper list from table using `parse_table()` or raw `CaseData.table`
  - [ ] 🟥 Cross-match: for each citation, attempt to match against table using `match_citation_to_table()`. Flag unmatched citations as fabricated
  - [ ] 🟥 Return `EvalResult` with: score=1.0 if no fabricated refs else 0.0, findings listing each fabricated ref as severity="error"
  - [ ] 🟥 Register with eval runner
  - [ ] 🟥 Test against `samples/case_001/` — must catch the intentionally planted fabricated reference

- [ ] 🟥 **Task 4: requirements.txt**
  - [ ] 🟥 Add dependencies: `openai` (for LLM client), `rapidfuzz` (for fuzzy matching in citation/table parser)
  - [ ] 🟥 Pin versions

- [ ] 🟥 **Task 5: End-to-end validation**
  - [ ] 🟥 Run `python -m evals.run samples/case_001/` — should execute AE-6 successfully
  - [ ] 🟥 Verify `samples/case_001/eval_results.json` is created with correct structure
  - [ ] 🟥 Verify AE-6 caught the fabricated reference in the sample data
