# Sprint: Foundation — LLM Infrastructure

**Overall Progress:** `0%`

## TLDR
Build the LLM judge base, claim extractor, and result schema. These are the LLM-side utilities that all LLM-based evals depend on.

## Context
- Eval strategy: `docs/EVAL_STRATEGY.md`
- All shared code goes in `evals/shared/`
- Python 3.11+, type hints encouraged
- This session runs in parallel with `SPRINT_FOUNDATION_PARSERS.md` — no cross-dependencies
- Claim extractor depends on LLM judge base — build LLM judge first within this session

## Interfaces Contract
Other sessions depend on these exact interfaces. Do not deviate.

```python
# evals/shared/llm_judge.py
class LLMJudge:
    def __init__(self): ...  # reads EVAL_LLM_BASE_URL, EVAL_LLM_API_KEY, EVAL_LLM_MODEL from env
    def judge(self, prompt: str, response_schema: dict) -> dict: ...
    def judge_with_rubric(self, prompt: str, rubric: dict[str, list[str]]) -> dict: ...

# evals/shared/claim_extractor.py
@dataclass
class Claim:
    text: str
    section: str
    citation: Citation | None  # Citation from evals/shared/citation_parser.py
    is_numerical: bool

def extract_claims(report: str, llm_judge: LLMJudge) -> list[Claim]: ...

# evals/shared/results.py
@dataclass
class Finding:
    severity: str  # "error" | "warning" | "info"
    message: str
    location: str | None

@dataclass
class EvalResult:
    eval_name: str
    score: float
    max_score: float
    passed: bool
    findings: list[Finding]
    reasoning: str

class CaseResults:
    results: list[EvalResult]
    def save(self, case_path: str) -> None: ...  # writes eval_results.json
    @classmethod
    def load(cls, case_path: str) -> "CaseResults": ...
```

## Dependency on Parsers Session
The claim extractor references `Citation` from `evals/shared/citation_parser.py`. Import it, but the `Citation` dataclass is simple — if the parsers session hasn't run yet, define a compatible `Citation` dataclass locally and it will be replaced when sessions merge. The contract is:

```python
@dataclass
class Citation:
    raw_text: str
    authors: list[str] | None
    year: int | None
    reference_id: str | None
```

## Tasks

- [ ] 🟥 **Task 1: LLM judge base** (`evals/shared/llm_judge.py`)
  - [ ] 🟥 `LLMJudge` class wrapping an LLM client (support OpenAI-compatible API via env var `EVAL_LLM_BASE_URL`, `EVAL_LLM_API_KEY`, `EVAL_LLM_MODEL`)
  - [ ] 🟥 `judge(prompt: str, response_schema: dict) -> dict` — send prompt, parse structured JSON response
  - [ ] 🟥 `judge_with_rubric(prompt: str, rubric: dict[str, list[str]]) -> dict` — score on multiple dimensions given a rubric
  - [ ] 🟥 Retry logic for malformed LLM responses (up to 2 retries)
  - [ ] 🟥 Logging: log each judge call's prompt and response for debugging

- [ ] 🟥 **Task 2: Result schema** (`evals/shared/results.py`)
  - [ ] 🟥 `EvalResult` dataclass: `eval_name: str`, `score: float`, `max_score: float`, `passed: bool`, `findings: list[Finding]`, `reasoning: str`
  - [ ] 🟥 `Finding` dataclass: `severity: str` (error/warning/info), `message: str`, `location: str | None` (section or line reference)
  - [ ] 🟥 `CaseResults` — aggregates all eval results for a case, serializes to `eval_results.json`
  - [ ] 🟥 `save_results(case_path: str, results: CaseResults)` and `load_results(case_path: str) -> CaseResults`

- [ ] 🟥 **Task 3: Claim extractor** (`evals/shared/claim_extractor.py`)
  - [ ] 🟥 `extract_claims(report: str, llm_judge: LLMJudge) -> list[Claim]` — use LLM to identify all factual/empirical claims in report
  - [ ] 🟥 `Claim` dataclass: `text: str`, `section: str`, `citation: Citation | None`, `is_numerical: bool`
  - [ ] 🟥 Prompt design: instruct LLM to return structured JSON array of claims with their section context and any attached citation
  - [ ] 🟥 Parse LLM output into Claim objects
