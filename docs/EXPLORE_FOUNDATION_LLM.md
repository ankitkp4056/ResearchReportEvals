# Exploration: Foundation LLM Infrastructure Sprint

**Date:** 2026-04-03  
**Sprint:** Foundation — LLM Infrastructure  
**Status:** Exploration Complete

---

## Scope Summary

This sprint builds three core LLM-side infrastructure components that serve as the foundation for all LLM-based evaluation utilities:

1. **LLMJudge class** — OpenAI-compatible LLM wrapper with structured output, rubric scoring, and retry logic
2. **Result schema** — Data classes for eval results (EvalResult, Finding, CaseResults) with JSON serialization
3. **Claim extractor** — LLM-powered utility to identify and structure factual claims in reports

These components are foundational: all downstream evals (AE-1 through AE-7) depend on LLMJudge and/or the result schema. The claim extractor specifically enables claim-level evals (AE-4, AE-5, AE-7).

**Deliverables:**
- `evals/shared/llm_judge.py` — LLMJudge class with judge() and judge_with_rubric() methods
- `evals/shared/results.py` — EvalResult, Finding, CaseResults dataclasses + JSON I/O
- `evals/shared/claim_extractor.py` — extract_claims() function + Claim dataclass

---

## Existing Context & Architecture

### Project Structure
The repository is a bare evaluation harness for a remote Scientific Research Agent. The agent produces artifacts per run:
- `query.txt` — user research query
- `todo.md` — planning doc
- `table.csv` — extraction table (papers × focus criteria)
- `report.md` — generated report with citations

Artifact samples live in `samples/case_NNN/` folders.

### Current State
- Repository initialized with docs and empty `evals/` package structure
- Directory `/tmp/sra-foundation-llm/` contains working files for this sprint
- Original repo at `/home/ankitkp4056/Documents/Projects/ankitkp4056/ResearchReportEvals/` has the same structure
- No Python code exists yet; all three sprint sessions (LLM, Parsers, Integration) start from scratch

### Parallel Sessions
This sprint runs in parallel with **SPRINT_FOUNDATION_PARSERS.md** with zero cross-dependencies within this phase. Both feed into **SPRINT_FOUNDATION_INTEGRATION.md** afterward.

---

## Interfaces Contract (Strict)

All interfaces below are **locked** — downstream evals depend on exact signatures. Deviations will break integration.

### LLMJudge (llm_judge.py)

```python
class LLMJudge:
    def __init__(self): 
        """Read EVAL_LLM_BASE_URL, EVAL_LLM_API_KEY, EVAL_LLM_MODEL from environment."""
        ...
    
    def judge(self, prompt: str, response_schema: dict) -> dict:
        """
        Send prompt + schema to LLM, parse structured JSON response.
        Args:
            prompt: Instruction for the LLM
            response_schema: JSON schema dict defining expected output structure
        Returns:
            Parsed response as dict matching response_schema
        Raises:
            ValueError: If response unparseable after retries
        """
        ...
    
    def judge_with_rubric(self, prompt: str, rubric: dict[str, list[str]]) -> dict:
        """
        Score on multiple dimensions given a rubric.
        Args:
            prompt: Instruction for the LLM
            rubric: dict mapping dimension_name -> list of scale values
                   e.g., {"question_captured": ["yes", "partial", "no"]}
        Returns:
            dict with keys matching rubric keys, values from rubric lists
        """
        ...
```

**Key behaviors:**
- Read env vars: `EVAL_LLM_BASE_URL`, `EVAL_LLM_API_KEY`, `EVAL_LLM_MODEL`
- Support OpenAI-compatible API (e.g., Ollama, local LLMs via base URL)
- Retry up to 2 times on malformed JSON responses
- Log each call: prompt + response for debugging

### Result Schema (results.py)

```python
@dataclass
class Finding:
    severity: str  # "error" | "warning" | "info"
    message: str
    location: str | None  # section/line reference, optional

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
    
    def save(self, case_path: str) -> None:
        """Write results to eval_results.json in case folder."""
        ...
    
    @classmethod
    def load(cls, case_path: str) -> "CaseResults":
        """Load from eval_results.json in case folder."""
        ...
```

**Key behaviors:**
- EvalResult must track both numeric score and pass/fail boolean
- Findings allow severity levels for prioritization
- CaseResults aggregates multiple EvalResult objects
- JSON serialization: case_path/eval_results.json format for downstream runners

### Claim Extractor (claim_extractor.py)

```python
@dataclass
class Claim:
    text: str
    section: str  # which section of report this claim appears in
    citation: Citation | None  # Reference from citation_parser.py; can be None
    is_numerical: bool

def extract_claims(report: str, llm_judge: LLMJudge) -> list[Claim]:
    """
    Use LLM to identify all factual/empirical claims in a report.
    Args:
        report: Full markdown report text
        llm_judge: LLMJudge instance for structured output
    Returns:
        List of Claim objects
    """
    ...
```

**Key behaviors:**
- Use LLMJudge.judge() with structured schema to extract claims
- Parse report sections from markdown headings
- Citation field references Citation class from parsers session (see dependency note below)
- is_numerical flag for numerical claims (used by downstream evals)
- Prompt design: instruct LLM to return JSON array with {text, section, citation, is_numerical}

---

## Dependencies

### Internal Dependencies (Within This Sprint)
- **LLMJudge must be built first** — claim_extractor depends on it
- No other intra-sprint dependencies

### External Dependencies (Other Sessions)

#### From Parsers Session (SPRINT_FOUNDATION_PARSERS.md)
- `Citation` dataclass from `evals/shared/citation_parser.py`
  ```python
  @dataclass
  class Citation:
      raw_text: str
      authors: list[str] | None
      year: int | None
      reference_id: str | None
  ```
- **Resolution strategy if parsers session hasn't finished:**
  - Define a compatible local Citation dataclass in claim_extractor.py initially
  - At integration (SPRINT_FOUNDATION_INTEGRATION.md), replace with import from citation_parser.py
  - This avoids blocking this sprint

#### Downstream Dependencies (After Integration)
- **Integration session** (SPRINT_FOUNDATION_INTEGRATION.md) imports all three components
- **Track A evals** (AE-1, AE-2, AE-3) use LLMJudge directly
- **Track B evals** (AE-4, AE-5, AE-7) use both LLMJudge and claim_extractor
- All evals use result schema (EvalResult, CaseResults) for output

### External Libraries
- `openai` or compatible client for LLM communication (OpenAI-compatible API)
- `json` (stdlib) for response parsing
- `logging` (stdlib) for debug logs
- Optional: `pydantic` for schema validation (not required; manual dict parsing acceptable)

---

## Key Decisions Resolved

### 1. LLM Client Library
**Decision:** Use `openai` Python library configured via environment variables for base URL, API key, and model name.

**Rationale:**
- Supports OpenAI-compatible APIs (Ollama, vLLM, local LLMs via custom base URL)
- Environment config allows runtime flexibility across dev/test/prod
- Simpler than building raw HTTP client

**Implementation notes:**
- OpenAI client can take custom `base_url` parameter for non-OpenAI endpoints
- Store env vars at __init__ time; don't re-read every call for efficiency

### 2. Retry Logic Scope
**Decision:** Retry only on **JSON parsing failures**, not on LLM errors or bad content.

**Rationale:**
- Up to 2 retries (3 attempts total) covers most transient formatting issues
- Logs each retry attempt with prompt/response for debugging
- Doesn't mask semantic issues (e.g., LLM refusal, nonsensical output)
- Integration (AE-6) will validate end-to-end with sample data

### 3. Citation Dataclass Definition
**Decision:** Claim extractor imports Citation from parsers session, but includes a fallback definition.

**Rationale:**
- Prevents circular dependency during parallel development
- At integration time, parsers session will provide the real Citation class
- Fallback ensures claim_extractor can still function during integration

### 4. JSON Serialization Format
**Decision:** CaseResults.save() writes simple JSON dict with list of EvalResult dicts.

**Rationale:**
- Dataclass to_dict() conversion is straightforward
- No need for custom JSON encoder if we use dataclasses.asdict()
- Human-readable format for debugging

---

## Edge Cases & Risks

### Edge Cases

#### 1. LLM Environment Variables Missing
- **Risk:** Import/init fails silently if env vars not set
- **Mitigation:** Raise ValueError in __init__ with clear message listing required vars
- **Test:** Add integration test checking error message

#### 2. Malformed LLM Response After 2 Retries
- **Risk:** ValueError raised; eval fails
- **Mitigation:** Document in eval runner to skip eval on LLMJudge failure, log error
- **Severity:** Acceptable — integration session handles graceful degradation

#### 3. Report with No Markdown Sections
- **Risk:** Claim extractor can't identify section context
- **Mitigation:** Fallback to generic section name (e.g., "unsectioned") if no headings found
- **Test:** Test on flat report without markdown structure

#### 4. Claim References Citation Not in Citation Parser Output
- **Risk:** Citation field partially populated; downstream evals must handle None
- **Mitigation:** Citation field is optional (Citation | None); all code must handle None
- **Design:** Claim extractor returns None for unmatched citations; evals decide how to handle

#### 5. Rubric with Numeric vs Categorical Values
- **Risk:** judge_with_rubric() must return values matching rubric spec
- **Mitigation:** Validate LLM output against rubric values; retry if mismatch
- **Test:** Unit test with various rubric formats

### Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|-----------|
| LLM response format drift over time | Medium | Log all responses; periodically spot-check; adjust prompts if needed |
| OpenAI API rate limiting | Low | Environment for custom base URL allows local/batched LLM |
| Claim extraction over/under-generates claims | Medium | Tune prompt in claim_extractor; validate with sample data in integration |
| Large reports → slow LLM calls | Low | No built-in timeout; integration session can add if needed |
| Conflicting Citation class definitions | Low | Use fallback strategy + test integration merge behavior |

---

## Ambiguities Clarified

### 1. Prompt Design Responsibility
**Q:** Who writes the actual LLM prompts (template strings)?  
**A:** LLMJudge provides the plumbing (API calls, retries, parsing). Evals write their own prompts and pass to judge(). For claim_extractor specifically, this sprint provides a sensible default prompt.

### 2. Response Schema Format
**Q:** What schema format does LLM expect — JSON Schema spec, or simple dict?  
**A:** Simple dict with keys → expected types. LLMJudge converts to human-readable instruction; LLM returns JSON matching structure.

### 3. Logging Detail
**Q:** How verbose should logging be?  
**A:** Log each judge call's prompt + response at DEBUG level. Integration can adjust verbosity.

### 4. JSON File Format
**Q:** Should eval_results.json include metadata (timestamp, runner version)?  
**A:** Keep minimal for now — just CaseResults.results array. Integration can extend if needed.

### 5. CaseResults Mutability
**Q:** Is CaseResults a container (list-like) or a dataclass with a results field?  
**A:** Dataclass with a results field (list[EvalResult]). Allows for future metadata (e.g., run timestamp).

---

## Files to Create/Modify

### This Sprint Creates
- `/tmp/sra-foundation-llm/evals/shared/llm_judge.py` — LLMJudge class
- `/tmp/sra-foundation-llm/evals/shared/results.py` — EvalResult, Finding, CaseResults
- `/tmp/sra-foundation-llm/evals/shared/claim_extractor.py` — Claim, extract_claims()

### This Sprint Does NOT Create (Other Sessions)
- `evals/shared/citation_parser.py` — Parsers session
- `evals/shared/table_parser.py` — Parsers session
- `evals/shared/loader.py` — Parsers session
- `samples/case_001/` — Parsers session
- `evals/run.py` — Integration session
- `evals/__init__.py`, `evals/shared/__init__.py` — Integration session

### Integration Merges
- Import Citation from parsers session in claim_extractor.py (currently fallback)
- Create __init__.py files and export interfaces
- Test end-to-end with sample data

---

## Testing Strategy (Scoped to This Sprint)

Each component should be testable independently:

1. **LLMJudge unit tests:**
   - Mock OpenAI client; verify judge() calls API with correct params
   - Test JSON parsing with valid/invalid responses
   - Test retry logic with failing then succeeding responses
   - Test judge_with_rubric() with various rubrics

2. **Result schema tests:**
   - Serialize/deserialize EvalResult and CaseResults to/from JSON
   - Verify Finding structure
   - Test save/load roundtrip

3. **Claim extractor tests:**
   - Mock LLMJudge; test prompt construction
   - Verify Claim dataclass creation
   - Test with sample reports (provide small test markdown snippets)
   - Test edge case: report with no sections

Note: Full integration testing (evals actually running on sample data) is the responsibility of the Integration session.

---

## Implementation Plan (High Level)

**Build order within this sprint:**
1. `llm_judge.py` — LLMJudge class with judge() and judge_with_rubric() methods
2. `results.py` — Data classes and JSON serialization
3. `claim_extractor.py` — Claim extraction using LLMJudge
4. Unit tests for all three (mock-based, no real LLM calls)

**Estimated work:**
- LLMJudge: ~200-300 lines (includes retries, logging, error handling)
- Results schema: ~150 lines (dataclasses + to_dict/from_dict)
- Claim extractor: ~200 lines (prompt design, LLMJudge integration, parsing)
- Tests: ~400 lines (comprehensive mocking)

**No blocking dependencies** within this sprint. All components can be developed in parallel if needed, but serial order (LLMJudge → results → claim extractor) is recommended for clarity.

---

## Open Questions for Clarification

None. All interfaces, dependencies, and decisions are clearly specified in sprint docs and have been resolved above.

---

## Ready for Implementation

This exploration confirms:
- ✅ All interfaces are clear and locked
- ✅ Dependencies are documented (parallel with Parsers, feeds to Integration)
- ✅ Fallback strategies for cross-session dependencies
- ✅ No blocking ambiguities
- ✅ Scope is well-bounded (3 files, ~550 lines of code)
- ✅ Testing strategy is clear
- ✅ Integration path is smooth

**Proceed to implementation stage.**
