# Feature Implementation Plan

**Overall Progress:** `100%`

## TLDR

Build the three foundational LLM-side utilities that all LLM-based evals depend on: an LLMJudge class wrapping an OpenAI-compatible API, a result schema (EvalResult/Finding/CaseResults) with JSON serialization, and a claim extractor that uses LLMJudge to identify factual claims in reports. These live in `evals/shared/` and are consumed by every downstream eval sprint.

## Exploration Summary

**Key findings from exploration (`docs/EXPLORE_FOUNDATION_LLM.md`):**

- **Current state:** Repository is bare -- no Python code exists yet. All three files are created from scratch.
- **Parallel session:** Runs alongside SPRINT_FOUNDATION_PARSERS (no cross-dependencies within this phase). Both feed into SPRINT_FOUNDATION_INTEGRATION afterward.
- **Citation dependency:** The claim extractor references `Citation` from `evals/shared/citation_parser.py` (parsers session). Since that session may not have run yet, define a compatible fallback `Citation` dataclass locally in `claim_extractor.py`. Integration session will replace it with the real import.
- **Build order constraint:** LLMJudge must be built first -- claim extractor depends on it. Results schema has no dependencies and can be built in parallel with LLMJudge.
- **External library:** Use the `openai` Python library configured via env vars (`EVAL_LLM_BASE_URL`, `EVAL_LLM_API_KEY`, `EVAL_LLM_MODEL`) for OpenAI-compatible API support.
- **Retry scope:** Retry only on JSON parsing failures (up to 2 retries, 3 attempts total). Do not retry on LLM errors or semantic issues.
- **Edge cases identified:** missing env vars (raise ValueError), malformed LLM response after retries (raise ValueError), reports with no markdown sections (fallback to "unsectioned"), rubric value validation against LLM output.
- **Interfaces are locked:** Downstream evals depend on exact signatures. No deviations allowed.
- **Estimated scope:** ~550 lines of implementation code across 3 files, plus ~400 lines of tests.

## Critical Decisions

- **Decision 1:** Use `openai` Python library with custom `base_url` -- supports OpenAI, Ollama, vLLM, and other compatible endpoints without custom HTTP code.
- **Decision 2:** Retry only on JSON parse failures (not LLM errors) -- avoids masking semantic issues while handling transient formatting problems.
- **Decision 3:** Define fallback `Citation` dataclass locally in claim_extractor.py -- prevents blocking on parsers session; replaced at integration.
- **Decision 4:** CaseResults.save() writes minimal JSON (just results array) -- no metadata overhead; integration can extend later.
- **Decision 5:** LLMJudge logs prompt + response at DEBUG level -- sufficient for debugging without excessive noise.

## Tasks

- [x] ✅ **Step 1: Create package structure**
  - [x] ✅ Create `evals/__init__.py` and `evals/shared/__init__.py` as empty files so imports work during development

- [x] ✅ **Step 2: Implement LLMJudge (`evals/shared/llm_judge.py`)**
  - [x] ✅ Implement `LLMJudge.__init__()` reading `EVAL_LLM_BASE_URL`, `EVAL_LLM_API_KEY`, `EVAL_LLM_MODEL` from env; raise `ValueError` if any are missing
  - [x] ✅ Implement `judge(prompt, response_schema)` -- send prompt to LLM with schema instruction, parse structured JSON response
  - [x] ✅ Implement `judge_with_rubric(prompt, rubric)` -- build schema from rubric dimensions, call LLM, validate returned values match rubric options
  - [x] ✅ Implement retry logic: up to 2 retries on JSON parse failures (3 attempts total), log each retry
  - [x] ✅ Add logging at DEBUG level for each call (prompt sent, response received)

- [x] ✅ **Step 3: Implement result schema (`evals/shared/results.py`)**
  - [x] ✅ Define `Finding` dataclass with `severity` (error/warning/info), `message`, `location` (optional)
  - [x] ✅ Define `EvalResult` dataclass with `eval_name`, `score`, `max_score`, `passed`, `findings`, `reasoning`
  - [x] ✅ Implement `CaseResults` with `results: list[EvalResult]`, `save(case_path)` writing `eval_results.json`, and `load(case_path)` classmethod
  - [x] ✅ Use `dataclasses.asdict()` for JSON serialization; implement `from_dict()` classmethods for deserialization

- [x] ✅ **Step 4: Implement claim extractor (`evals/shared/claim_extractor.py`)**
  - [x] ✅ Define fallback `Citation` dataclass (matching parsers session contract: `raw_text`, `authors`, `year`, `reference_id`) with try/except import from `evals.shared.citation_parser`
  - [x] ✅ Define `Claim` dataclass with `text`, `section`, `citation` (Citation | None), `is_numerical`
  - [x] ✅ Implement `extract_claims(report, llm_judge)` -- build prompt instructing LLM to return JSON array of claims with section context, citation info, and numerical flag
  - [x] ✅ Parse LLM JSON output into `Claim` objects; handle edge case of reports with no markdown headings (fallback section name "unsectioned")

- [x] ✅ **Step 5: Write unit tests**
  - [x] ✅ LLMJudge tests: mock OpenAI client; test judge() with valid/invalid responses, retry logic, judge_with_rubric() with various rubrics, missing env vars error
  - [x] ✅ Results tests: serialize/deserialize roundtrip for Finding, EvalResult, CaseResults; test save/load to filesystem
  - [x] ✅ Claim extractor tests: mock LLMJudge; test prompt construction, Claim creation, edge case with no sections

- [x] ✅ **Step 6: Add `openai` to requirements.txt**
  - [x] ✅ Create or update `requirements.txt` with `openai` dependency
