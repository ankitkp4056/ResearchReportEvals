# Feature Implementation Plan

**Overall Progress:** `100%`

## TLDR

Build three claim-level artifact evals (AE-4 Citation Completeness, AE-5 Citation Correctness, AE-7 Grounding Check) that verify whether factual claims in the research report are properly cited and grounded in source papers. All three share a common pattern: extract claims via `ClaimExtractor`, then evaluate each claim against the extraction table and/or via LLM judge. Each eval follows the `fabricated_references.py` pattern and registers with `evals/run.py`.

## Exploration Summary

**Key files and APIs (all in `evals/shared/`):**

- `loader.py` -- `load_case(case_path) -> CaseData` with `.report` (str), `.table` (list[dict]), `.plan` (str), `.query` (str)
- `claim_extractor.py` -- `extract_claims(report: str, llm_judge: LLMJudge) -> list[Claim]` where `Claim` has `.text`, `.section`, `.citation` (Citation | None), `.is_numerical`
- `citation_parser.py` -- `Citation` (`.raw_text`, `.authors`, `.year`, `.reference_id`), `extract_citations()`, `match_citation_to_table(citation, table) -> dict | None`
- `table_parser.py` -- `parse_table(csv_path) -> list[PaperRecord]` where `PaperRecord` has `.title`, `.authors`, `.year`, `.abstract`, `.focus_columns` (dict)
- `llm_judge.py` -- `LLMJudge()` instantiated from env vars, `.judge(prompt, response_schema) -> dict`
- `results.py` -- `EvalResult(eval_name, score, max_score, passed, findings, reasoning)`, `Finding(severity, message, location)`

**Reference pattern (fabricated_references.py):**
- Module-level `EVAL_NAME` and `REQUIRED_ARTIFACTS` constants
- Single `evaluate_*()` function taking `CaseData`, returning `EvalResult`
- `__main__` block for standalone execution with `load_case(sys.argv[1])`
- Registration in `evals/run.py` via `register_eval(name, fn, artifacts)`

**Registration pattern (evals/run.py):**
- Import `EVAL_NAME`, `REQUIRED_ARTIFACTS`, and the evaluate function from the module
- Call `register_eval(name, fn, artifacts)` at module level

**Key consideration -- LLM dependency:**
AE-4 uses `extract_claims()` which requires an `LLMJudge` instance. AE-5 and AE-7 additionally use `LLMJudge` directly for verdict prompts. All three evals require `EVAL_LLM_BASE_URL`, `EVAL_LLM_API_KEY`, and `EVAL_LLM_MODEL` environment variables set at runtime.

**Key consideration -- numeric citation matching:**
The sample data uses numeric citations `[1]`-`[30]`. `match_citation_to_table()` returns None for numeric refs. The `fabricated_references.py` eval handles this by mapping `[N]` to table row index N-1. AE-5 will need the same numeric-index strategy since it must resolve citations to paper records.

**Key consideration -- AE-7 prompt size:**
Grounding check sends each claim against ALL paper records. With 30+ papers, the prompt will be large. Paper summaries should be kept concise (title + abstract snippet + focus columns) to stay within context limits.

## Critical Decisions

- Decision 1: AE-4 evaluate function accepts `CaseData` only (not LLMJudge) -- instantiate `LLMJudge()` inside the function body, consistent with the pattern where eval functions have a uniform `(CaseData) -> EvalResult` signature for registry compatibility
- Decision 2: AE-5 resolves numeric citations `[N]` to table row N-1 (same strategy as AE-6) rather than relying on `match_citation_to_table()` which returns None for numeric refs
- Decision 3: AE-7 builds concise paper summaries (title, authors, year, abstract truncated to ~200 chars, focus column values) to keep prompt size manageable across 30+ papers
- Decision 4: Score thresholds -- AE-4 passes if completeness >= 0.8, AE-5 passes if correctness >= 0.7, AE-7 passes if grounding >= 0.7 (these are reasonable starting thresholds; tunable later)
- Decision 5: All three evals strip the References section from the report before extracting claims (same as AE-6) to avoid evaluating the reference list itself

## Tasks

- [x] **Step 1: AE-4 -- Citation Completeness** (`evals/artifact/citation_completeness.py`)
  - [x] Define `EVAL_NAME = "ae-4"` and `REQUIRED_ARTIFACTS = ["report"]`
  - [x] Implement `evaluate_citation_completeness(case: CaseData) -> EvalResult`
    - Instantiate `LLMJudge()`, call `extract_claims(report, llm_judge)`
    - Strip references section before extraction
    - Partition claims into cited (`.citation is not None`) vs uncited
    - Compute `score = cited_count / total_count` (or 1.0 if no claims)
    - Create `Finding(severity="warning", message=..., location=section)` for each uncited claim
    - Return `EvalResult` with score, `max_score=1.0`, `passed=(score >= 0.8)`
  - [x] Add `__main__` block: load case from `sys.argv[1]`, run eval, print results
  - [x] Register in `evals/run.py` following the AE-6 import pattern

- [x] **Step 2: AE-5 -- Citation Correctness** (`evals/artifact/citation_correctness.py`)
  - [x] Define `EVAL_NAME = "ae-5"` and `REQUIRED_ARTIFACTS = ["report", "table"]`
  - [x] Implement helper `_resolve_citation_to_paper(citation, table_rows, paper_records)` that handles both numeric refs (index mapping) and author-year refs (via `match_citation_to_table`)
  - [x] Implement `_build_correctness_prompt(claim_text, paper_record)` -- asks LLM to judge whether the paper supports the claim; expects response with `verdict` (supports/partially_supports/contradicts/unrelated) and `reasoning`
  - [x] Implement `evaluate_citation_correctness(case: CaseData) -> EvalResult`
    - Instantiate `LLMJudge()`, extract claims, filter to cited-only
    - For each cited claim: resolve citation to paper, send to LLM judge
    - Score mapping: supports=1.0, partially_supports=0.5, contradicts=0.0, unrelated=0.0
    - Average scores across all cited claims for final score
    - Create findings for contradicts/unrelated verdicts (severity="error") and partially_supports (severity="warning")
    - Return `EvalResult` with `max_score=1.0`, `passed=(score >= 0.7)`
  - [x] Add `__main__` block
  - [x] Register in `evals/run.py`

- [x] **Step 3: AE-7 -- Grounding Check** (`evals/artifact/grounding_check.py`)
  - [x] Define `EVAL_NAME = "ae-7"` and `REQUIRED_ARTIFACTS = ["report", "table"]`
  - [x] Implement helper `_build_paper_summaries(paper_records)` -- produces a concise text block summarizing all papers (title, authors, year, truncated abstract, focus columns)
  - [x] Implement `_build_grounding_prompt(claim_text, paper_summaries)` -- asks LLM whether the claim is grounded in any of the source papers; expects `verdict` (grounded/partially_grounded/ungrounded) and `reasoning`
  - [x] Implement `evaluate_grounding_check(case: CaseData) -> EvalResult`
    - Instantiate `LLMJudge()`, extract all claims (cited and uncited)
    - Build paper summaries once from `parse_table()`
    - For each claim: send to LLM with all paper summaries
    - Score mapping: grounded=1.0, partially_grounded=0.5, ungrounded=0.0
    - Average scores for final score
    - Create findings for ungrounded (severity="error") and partially_grounded (severity="warning")
    - Return `EvalResult` with `max_score=1.0`, `passed=(score >= 0.7)`
  - [x] Add `__main__` block
  - [x] Register in `evals/run.py`

- [x] **Step 4: Verify runner integration**
  - [x] Confirm all modules import successfully without syntax errors
  - [x] Confirm all evals are registered in EVAL_REGISTRY (ae-4, ae-5, ae-6, ae-7)
  - [x] Confirm artifact requirements are correct for each eval
  - [x] Confirm sample case loads successfully with all required artifacts
  - [x] Confirm standalone entry points display usage messages correctly
  - [x] Confirm _has_artifacts() check passes for all evals on sample case
  - [ ] Full integration test (requires LLM env vars): `python -m evals.run samples/case_001/ --only ae-4`
  - [ ] Full integration test (requires LLM env vars): `python -m evals.run samples/case_001/ --only ae-5`
  - [ ] Full integration test (requires LLM env vars): `python -m evals.run samples/case_001/ --only ae-7`
  - [ ] Full integration test (requires LLM env vars): `python -m evals.artifact.citation_completeness samples/case_001/`

---

## Implementation Summary

All three claim-level artifact evals have been successfully implemented and registered with the eval runner.

### Files Created

1. `/tmp/sra-track-b/evals/artifact/citation_completeness.py` (129 lines)
   - AE-4: Citation Completeness eval
   - Measures what fraction of factual claims have citations
   - Score threshold: 0.8 (passes if >= 80% of claims are cited)

2. `/tmp/sra-track-b/evals/artifact/citation_correctness.py` (252 lines)
   - AE-5: Citation Correctness eval
   - Uses LLM judge to verify each cited claim is supported by its cited paper
   - Handles both numeric `[N]` and author-year citations
   - Score threshold: 0.7 (passes if >= 70% of cited claims are correctly supported)

3. `/tmp/sra-track-b/evals/artifact/grounding_check.py` (203 lines)
   - AE-7: Grounding Check eval
   - Uses LLM judge to verify all claims (cited or uncited) are grounded in source papers
   - Detects hallucinations (claims with no support in any paper)
   - Score threshold: 0.7 (passes if >= 70% of claims are grounded)

### Files Modified

1. `/tmp/sra-track-b/evals/run.py`
   - Registered all three new evals (ae-4, ae-5, ae-7) following the AE-6 pattern
   - All evals now available via `python -m evals.run <case_path> --only <eval-name>`

### Verification Completed

- All modules import successfully without syntax errors
- All evals registered correctly in EVAL_REGISTRY
- Artifact requirements validated (ae-4: report only; ae-5 & ae-7: report + table)
- Sample case (case_001) loads successfully with all required artifacts
- Standalone entry points work correctly and display proper usage messages
- _has_artifacts() checks pass for all evals on sample case

### Remaining Work

Full integration testing requires setting environment variables:
- `EVAL_LLM_BASE_URL` (e.g., "https://api.openai.com/v1")
- `EVAL_LLM_API_KEY` (API key for the LLM service)
- `EVAL_LLM_MODEL` (model name, e.g., "gpt-4")

Once these are set, run:
```bash
python -m evals.run samples/case_001/ --only ae-4
python -m evals.run samples/case_001/ --only ae-5
python -m evals.run samples/case_001/ --only ae-7
```

Or run individual evals standalone:
```bash
python -m evals.artifact.citation_completeness samples/case_001/
python -m evals.artifact.citation_correctness samples/case_001/
python -m evals.artifact.grounding_check samples/case_001/
```

### Design Highlights

1. **Consistent Pattern**: All three evals follow the fabricated_references.py pattern exactly
2. **Proper Citation Handling**: AE-5 correctly handles both numeric `[N]` citations (via index mapping) and author-year citations (via fuzzy matching)
3. **Efficient Prompting**: AE-7 builds concise paper summaries (~200 char abstracts) to keep prompt size manageable with 30+ papers
4. **References Stripping**: All evals strip the References section before claim extraction to avoid false positives
5. **Graduated Severity**: Findings use appropriate severity levels (error for contradictions/ungrounded claims, warning for partial support)
6. **Standalone Execution**: Each eval can be run independently with its own __main__ block
