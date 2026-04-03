# Sprint: Track A — Plan + Structure Evals

**Overall Progress:** `0%`

## TLDR
Build the three artifact evals that assess whether the report followed the plan. These evals only need `query.txt`, `todo.md`, and `report.md` — no dependency on table.csv or source papers.

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
- Use shared `LLMJudge` from `evals/shared/llm_judge.py` for all LLM calls
- Return `EvalResult` from `evals/shared/results.py`

## Tasks

- [ ] 🟥 **Task 1: AE-1 — Planning Faithfulness** (`evals/artifact/planning_faithfulness.py`)
  - [ ] 🟥 Load case, extract `query.txt` and `todo.md`
  - [ ] 🟥 Design rubric with 3 dimensions:
    - Research question captured? (yes=1.0 / partial=0.5 / no=0.0)
    - Purpose identified? (survey / comparison / deep-dive / other — score 1.0 if correctly identified, 0.0 if wrong/missing)
    - Scope appropriate? (too broad=0.3 / just right=1.0 / too narrow=0.3)
  - [ ] 🟥 Build LLM prompt: provide query + plan, ask LLM to score each dimension with reasoning
  - [ ] 🟥 Parse LLM response into `EvalResult` — overall score = average of 3 dimensions
  - [ ] 🟥 Register with eval runner
  - [ ] 🟥 Test against `samples/case_001/`

- [ ] 🟥 **Task 2: AE-2 — Section Coverage** (`evals/artifact/section_coverage.py`)
  - [ ] 🟥 Load case, extract `todo.md` and `report.md`
  - [ ] 🟥 Script step: extract section headings / topic areas from `todo.md` (parse markdown headings + bullet points that describe research areas)
  - [ ] 🟥 Script step: extract section headings from `report.md`
  - [ ] 🟥 LLM step: given plan sections and report sections, map each plan topic to report sections. Identify: covered, partially covered, missing
  - [ ] 🟥 Compute coverage score: `fully_covered * 1.0 + partially * 0.5 + missing * 0.0` / total plan topics
  - [ ] 🟥 Return `EvalResult` with coverage percentage + findings listing missing/underexplored areas
  - [ ] 🟥 Register with eval runner
  - [ ] 🟥 Test against `samples/case_001/`

- [ ] 🟥 **Task 3: AE-3 — Analysis Depth** (`evals/artifact/analysis_depth.py`)
  - [ ] 🟥 Load case, extract `query.txt` and `report.md`
  - [ ] 🟥 Step 1: LLM classifies query purpose — survey (breadth), comparison (cross-paper synthesis), deep-dive (detailed few papers)
  - [ ] 🟥 Step 2: Based on classified purpose, apply purpose-specific rubric:
    - Survey → score on: number of papers mentioned, breadth of topics, conciseness per paper
    - Comparison → score on: cross-paper analysis, dimensions compared, synthesis quality
    - Deep-dive → score on: depth per paper, methodology discussion, limitations covered
  - [ ] 🟥 LLM scores depth on 1-5 scale with reasoning
  - [ ] 🟥 Return `EvalResult` with purpose classification + depth score (normalized to 0-1) + reasoning
  - [ ] 🟥 Register with eval runner
  - [ ] 🟥 Test against `samples/case_001/`
