# Sprint: Track B — Claim-Level Evals

**Overall Progress:** `0%`

## TLDR
Build the three artifact evals that verify whether claims in the report are properly cited and grounded in source papers. These evals all consume claims + citations extracted by the shared parsers.

## Prerequisites
- Foundation sprint (`docs/SPRINT_FOUNDATION.md`) must be complete
- Shared utilities exist in `evals/shared/`: loader, llm_judge, results, claim_extractor, citation_parser, table_parser
- Eval runner + CLI working at `evals/run.py`
- Sample test data in `samples/case_001/`

## Context
- Eval strategy: `docs/EVAL_STRATEGY.md`
- All eval code goes in `evals/artifact/`
- Python 3.11+, type hints encouraged
- Each eval must be runnable standalone: `python -m evals.artifact.<module_name> samples/case_001/`
- Each eval must register with the eval runner in `evals/run.py`
- Use shared `ClaimExtractor` from `evals/shared/claim_extractor.py` — all three evals start by extracting claims
- Use shared `LLMJudge` from `evals/shared/llm_judge.py` for all LLM calls
- Return `EvalResult` from `evals/shared/results.py`

## Tasks

- [ ] 🟥 **Task 1: AE-4 — Citation Completeness** (`evals/artifact/citation_completeness.py`)
  - [ ] 🟥 Load case, extract `report.md`
  - [ ] 🟥 Use claim extractor to get all factual/empirical claims from report
  - [ ] 🟥 For each claim, check if it has an attached citation (using the `citation` field on `Claim`)
  - [ ] 🟥 Compute completeness ratio: `cited_claims / total_claims`
  - [ ] 🟥 Return `EvalResult` with completeness ratio as score + findings listing each uncited claim (severity=warning, location=section)
  - [ ] 🟥 Register with eval runner
  - [ ] 🟥 Test against `samples/case_001/` — should flag the intentionally uncited claim

- [ ] 🟥 **Task 2: AE-5 — Citation Correctness** (`evals/artifact/citation_correctness.py`)
  - [ ] 🟥 Load case, extract `report.md` and `table.csv`
  - [ ] 🟥 Use claim extractor to get all cited claims
  - [ ] 🟥 For each cited claim:
    1. Match the citation to a paper in table.csv using citation parser's `match_citation_to_table`
    2. If matched, send claim + paper record (title, abstract, focus columns) to LLM
    3. LLM judges: supports / partially supports / contradicts / unrelated
  - [ ] 🟥 Score mapping: supports=1.0, partially=0.5, contradicts=0.0, unrelated=0.0
  - [ ] 🟥 Compute correctness ratio: average score across all cited claims
  - [ ] 🟥 Return `EvalResult` with correctness ratio + findings for each incorrect/unrelated citation with LLM reasoning
  - [ ] 🟥 Register with eval runner
  - [ ] 🟥 Test against `samples/case_001/` — should catch the intentionally wrong citation

- [ ] 🟥 **Task 3: AE-7 — Grounding Check** (`evals/artifact/grounding_check.py`)
  - [ ] 🟥 Load case, extract `report.md` and `table.csv` (for source paper content)
  - [ ] 🟥 Use claim extractor to get all claims (cited and uncited)
  - [ ] 🟥 For each claim:
    1. Gather all paper records from table as potential sources
    2. Send claim + all paper summaries (title, abstract, focus columns) to LLM
    3. LLM classifies: grounded (evidence found in sources) / partially grounded / ungrounded (no source supports this)
  - [ ] 🟥 Score mapping: grounded=1.0, partially=0.5, ungrounded=0.0
  - [ ] 🟥 Compute grounding rate: average score across all claims
  - [ ] 🟥 Return `EvalResult` with grounding rate + findings listing each ungrounded claim with reasoning
  - [ ] 🟥 Note: A claim can fail AE-5 (wrong citation) but pass AE-7 (content is grounded, just cited wrong paper). This is expected.
  - [ ] 🟥 Register with eval runner
  - [ ] 🟥 Test against `samples/case_001/`
