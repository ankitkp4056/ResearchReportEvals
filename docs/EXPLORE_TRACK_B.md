# Exploration: Track B — Claim-Level Evals

## Scope Summary

Track B implements three artifact-level evaluations that verify whether claims in research reports are properly cited and grounded in source papers. All three evals follow the same structural pattern:

1. **AE-4 (Citation Completeness)**: Measures what fraction of factual claims have citations (citation_completeness_ratio)
2. **AE-5 (Citation Correctness)**: Verifies that cited papers actually support the claims made (correctness_ratio)
3. **AE-7 (Grounding Check)**: Ensures all claims (cited or not) are traceable to source papers in the extraction table (grounding_rate)

All three evals consume:
- Report markdown (`case.report`)
- Extraction table in CSV format (`case.table`)
- Claim extractor (LLM-based)
- LLM judge (for correctness/grounding validation)
- Citation parser (for matching citations to papers)
- Table parser (for structured access to paper records)

---

## Relevant Existing Files and Their Roles

### Shared Infrastructure (evals/shared/)

#### 1. loader.py — CaseData
**Location:** `/home/ankitkp4056/Documents/Projects/ankitkp4056/ResearchReportEvals/evals/shared/loader.py`

**API:**
```python
@dataclass
class CaseData:
    query: str               # raw user query
    plan: str                # planning doc (todo.md)
    table: list[dict]        # CSV rows as dicts (key=header name)
    report: str              # report markdown
    case_path: Path          # absolute path to case directory

def load_case(case_path: str) -> CaseData:
    """Load all four artifacts from a case directory.
    
    Raises: FileNotFoundError, ValueError
    """
```

**Usage Pattern:** Entry point for all evals. Load once at start of eval function.

---

#### 2. results.py — EvalResult, Finding, CaseResults
**Location:** `/home/ankitkp4056/Documents/Projects/ankitkp4056/ResearchReportEvals/evals/shared/results.py`

**API:**
```python
@dataclass
class Finding:
    severity: str           # "error" | "warning" | "info"
    message: str            # human-readable description
    location: str | None    # optional reference (section, line, citation id)

@dataclass
class EvalResult:
    eval_name: str          # e.g. "ae-4"
    score: float            # numeric score (>=0)
    max_score: float        # max achievable (typically 1.0)
    passed: bool            # True if score >= threshold
    findings: list[Finding] # individual findings (default [])
    reasoning: str          # free-text explanation (default "")
```

**Usage Pattern:** Construct EvalResult at end of eval function with computed score, list of findings, and reasoning. Return to runner.

---

#### 3. llm_judge.py — LLMJudge
**Location:** `/home/ankitkp4056/Documents/Projects/ankitkp4056/ResearchReportEvals/evals/shared/llm_judge.py`

**API:**
```python
class LLMJudge:
    """Requires env vars: EVAL_LLM_BASE_URL, EVAL_LLM_API_KEY, EVAL_LLM_MODEL"""
    
    def judge(self, prompt: str, response_schema: dict) -> dict:
        """Send prompt, get structured JSON response.
        
        Args:
            prompt: Evaluation prompt describing the task
            response_schema: dict mapping field names to descriptions
                Example: {"score": "integer 1-5", "reasoning": "brief explanation"}
        
        Returns:
            Parsed dict matching response_schema keys
        
        Raises: ValueError if JSON parsing fails after retries
        """
    
    def judge_with_rubric(
        self, 
        prompt: str, 
        rubric: dict[str, list[str]]
    ) -> dict:
        """Score against multi-dimension rubric with ordered options.
        
        Args:
            prompt: Evaluation prompt
            rubric: dict mapping dimension names to ordered value lists
                Example: {"clarity": ["poor", "fair", "good"], 
                          "depth": ["shallow", "deep"]}
        
        Returns:
            Dict mapping each dimension to selected value + "reasoning" key
        
        Raises: ValueError if LLM selects invalid value for any dimension
        """
```

**Configuration:** Reads from environment at initialization. No credentials in code.
**Retry Logic:** Auto-retries up to 2 times on JSON parse failure.

---

#### 4. claim_extractor.py — Claim Extraction
**Location:** `/home/ankitkp4056/Documents/Projects/ankitkp4056/ResearchReportEvals/evals/shared/claim_extractor.py`

**API:**
```python
@dataclass
class Claim:
    text: str                    # verbatim sentence/clause
    section: str                 # markdown heading or "unsectioned"
    citation: Citation | None    # inline citation if present
    is_numerical: bool           # True if claim has numbers + units/stats

@dataclass
class Citation:
    """Fallback definition (authoritative in citation_parser.py)"""
    raw_text: str
    authors: list[str] | None
    year: int | None
    reference_id: str | None

def extract_claims(report: str, llm_judge: LLMJudge) -> list[Claim]:
    """Extract all factual/empirical claims from markdown report.
    
    Args:
        report: Full markdown text
        llm_judge: Configured LLMJudge instance
    
    Returns:
        List of Claim objects, one per identified factual statement.
        Each claim has: text, section, citation (or None), is_numerical flag.
    """
```

**Behavior:**
- Uses LLMJudge to identify claims via prompt with [SECTION: ...] tags
- Automatically detects citations in claim text using regex fallback
- Flags numerical claims (digits + units/stats) via regex backup
- Returns empty list if LLM response is malformed

**Citation Parsing:** Handles three formats:
- Numeric: `[1]`, `[12]` → reference_id set
- Author-year brackets: `[Smith, 2021]` → authors, year set
- Author-year narrative: `Smith (2021)` → authors, year set

---

#### 5. citation_parser.py — Citation Matching
**Location:** `/home/ankitkp4056/Documents/Projects/ankitkp4056/ResearchReportEvals/evals/shared/citation_parser.py`

**API:**
```python
@dataclass
class Citation:
    raw_text: str                      # full match as appeared in text
    authors: list[str] | None          # surname tokens or None for numeric
    year: int | None                   # publication year or None
    reference_id: str | None = None    # numeric ref id (e.g. "7")

def extract_citations(report: str) -> list[Citation]:
    """Extract all inline citations from report string.
    
    Parses parenthetical author-year, bracket author-year, and numeric refs.
    Results are deduplicated by raw_text and returned in order of first appearance.
    
    Returns: List[Citation], ordered by first appearance, deduplicated
    """

def match_citation_to_table(
    citation: Citation,
    table: list[dict],  # raw CSV rows from csv.DictReader
) -> dict | None:
    """Attempt to match Citation to a row in extraction table.
    
    Matching strategy:
    - Author-year: find first row where any cited surname appears in Authors column
                   AND Year column equals citation.year (case-insensitive, both must match)
    - Numeric: return None (cannot resolve without explicit ref list)
    
    Column lookup is case-insensitive.
    
    Args:
        citation: Citation object to resolve
        table: Raw list[dict] from loader (csv.DictReader rows)
    
    Returns:
        First matching table row dict (same as input), or None
    """
```

**Key Note:** `match_citation_to_table()` expects raw table dicts from loader, NOT parsed PaperRecord objects. Case-insensitive column matching.

---

#### 6. table_parser.py — Structured Table Access
**Location:** `/home/ankitkp4056/Documents/Projects/ankitkp4056/ResearchReportEvals/evals/shared/table_parser.py`

**API:**
```python
@dataclass
class PaperRecord:
    title: str
    authors: str
    year: int
    doi: str | None
    abstract: str | None
    focus_columns: dict[str, str]  # all non-metadata columns preserved with original headers

def parse_table(csv_path: str) -> list[PaperRecord]:
    """Parse table.csv into list of PaperRecord objects.
    
    Column names matched case-insensitively against metadata set:
    {title, authors, year, doi, abstract}
    
    All other columns stored in focus_columns with original header names preserved.
    
    Raises:
        FileNotFoundError: csv_path does not exist
        ValueError: missing required columns (title, authors, year) or year not an integer
    """

def get_paper_by_title(
    table: list[PaperRecord],
    query: str,
    threshold: float = 0.6,
) -> PaperRecord | None:
    """Fuzzy-match query string against paper titles (case-insensitive).
    
    Returns: Best-matching PaperRecord if similarity >= threshold, else None
    """
```

**Usage:** Can be used for AE-7 to build summaries of papers, but NOT for matching citations (use raw table with `match_citation_to_table()` instead).

---

### Eval Runner (evals/run.py)

**Location:** `/home/ankitkp4056/Documents/Projects/ankitkp4056/ResearchReportEvals/evals/run.py`

**Registry Pattern:**
```python
EVAL_REGISTRY: dict[str, dict] = {}  # name -> {fn, required_artifacts}

def register_eval(
    name: str,
    fn: Callable[[CaseData], EvalResult],
    required_artifacts: list[str],
) -> None:
    """Register an eval function in global registry."""

# At module level (bottom of run.py), import and register:
from evals.artifact.fabricated_references import (
    EVAL_NAME as _ae6_name,
    REQUIRED_ARTIFACTS as _ae6_artifacts,
    evaluate_fabricated_references as _ae6_fn,
)
register_eval(_ae6_name, _ae6_fn, _ae6_artifacts)
```

**Required Artifacts:** List of CaseData attribute names that must be non-empty. Supported keys:
- `"report"` → `case.report`
- `"table"` → `case.table`
- `"plan"` → `case.plan`
- `"query"` → `case.query`

**Runner Behavior:**
- Loads case from case_path
- Skips evals whose required artifacts are missing
- Catches exceptions, converts to EvalResult with score=0.0, passed=False
- Writes aggregated results to `{case_path}/eval_results.json`

---

### Pattern Example: AE-6 Fabricated References

**Location:** `/home/anzittkp4056/Documents/Projects/ankitkp4056/ResearchReportEvals/evals/artifact/fabricated_references.py`

**Structure:**
```python
EVAL_NAME = "ae-6"
REQUIRED_ARTIFACTS = ["report", "table"]

def evaluate_fabricated_references(case: CaseData) -> EvalResult:
    """Run the AE-6 fabricated-references eval.
    
    Returns EvalResult with:
    - score 1.0 if all citations resolve to table
    - score 0.0 if any citation is unmatched
    - findings listing each fabricated citation (severity=error)
    """
    # 1. Load data (strip References section)
    body = _strip_references_section(case.report)
    citations = extract_citations(body)
    table = case.table
    
    # 2. Check each citation against table
    findings: list[Finding] = []
    for cit in citations:
        if not _citation_matches_table(cit, table):
            findings.append(Finding(
                severity="error",
                message=f"Fabricated reference: {cit.raw_text} has no matching paper in table",
                location=cit.raw_text,
            ))
    
    # 3. Score and return
    score = 1.0 if not findings else 0.0
    return EvalResult(
        eval_name=EVAL_NAME,
        score=score,
        max_score=1.0,
        passed=score == 1.0,
        findings=findings,
        reasoning=f"Checked {len(citations)} citations. {len(findings)} fabricated.",
    )

# Standalone entry point for testing:
if __name__ == "__main__":
    case = load_case(sys.argv[1])
    result = evaluate_fabricated_references(case)
    print(f"AE-6 Score: {result.score}/{result.max_score}")
    # ... print findings
```

**Key Patterns:**
1. Define module-level constants: `EVAL_NAME`, `REQUIRED_ARTIFACTS`
2. Implement eval function: `evaluate_<name>(case: CaseData) -> EvalResult`
3. Return fully-constructed EvalResult with score, passed, findings, reasoning
4. Optionally add `if __name__ == "__main__"` block for standalone testing
5. Register at bottom of evals/run.py (import and register_eval call)

---

## Sample Data Structure

**Location:** `/home/ankitkp4056/Documents/Projects/ankitkp4056/ResearchReportEvals/samples/case_001/`

- **query.txt:** Raw user query (1-3 sentences)
- **todo.md:** Planning document (section-based research plan)
- **report.md:** Generated report (300+ sections with citations)
  - Contains inline citations in formats: `[5]`, `[Smith, 2021]`, `(Johnson et al., 2019)`
  - Has References section at end (to be stripped for some evals)
  - Well-formed markdown with ## headings
- **table.csv:** 2520 rows of paper metadata
  - Headers: Paper Title, Author Names, Publication Year, Abstract, AI Methodology, Performance Metrics, etc.
  - Case-insensitive column matching

**Sample Report Snippet:**
```
## 2. Background and Theoretical Foundations

### 2.1 The Clinical Need for AI in Cancer Detection

Early cancer detection significantly improves treatment outcomes...
false-negative rates in mammography range from 10–30% [5]. 
Similar challenges exist... creating an urgent need [5], [14].
```

**Sample Table Row:**
```
"Paper Title","Author Names","Publication Year",...
"Improving Early Prostate Cancer Detection...","Ciccone, G., et al.","2025",...
```

---

## Dependencies and Integration Points

### Internal Dependencies
1. **evals.shared.loader** → CaseData, load_case()
2. **evals.shared.results** → EvalResult, Finding
3. **evals.shared.llm_judge** → LLMJudge
4. **evals.shared.claim_extractor** → extract_claims(), Claim, Citation
5. **evals.shared.citation_parser** → extract_citations(), match_citation_to_table()
6. **evals.shared.table_parser** → parse_table(), PaperRecord

### External Dependencies
- **openai** (>=1.0.0) — for LLM API calls via LLMJudge
- **rapidfuzz** (>=3.0.0) — for fuzzy matching in table_parser.get_paper_by_title()
- **pytest** (>=7.0.0) — for unit tests

### Environment Variables (LLMJudge)
```bash
EVAL_LLM_BASE_URL    # e.g. https://api.openai.com/v1 or local Ollama URL
EVAL_LLM_API_KEY     # API key (dummy value for keyless endpoints)
EVAL_LLM_MODEL       # model name (e.g. gpt-4, gpt-3.5-turbo, ollama model name)
```

---

## Key Decisions and Ambiguities Resolved

### 1. Claim Extraction Responsibility
**Decision:** All three Track B evals start by calling `extract_claims()` independently.
- AE-4 uses claims to count citations
- AE-5 uses cited claims for correctness checking
- AE-7 uses all claims for grounding checking

**Rationale:** Each eval has different filtering/processing needs. No shared cost since extraction is fast relative to LLM calls.

### 2. Citation Matching Uses Raw Table, Not PaperRecord
**Decision:** `match_citation_to_table()` takes raw `list[dict]` from loader, not parsed `list[PaperRecord]`.
- For AE-5 correctness checking, need to send full paper data to LLM
- Use `parse_table()` to get structured access when needed

**Rationale:** Separate concerns — citation matching is structural; content analysis (AE-5, AE-7) requires PaperRecord.

### 3. Scoring Methodology
**Decision:** 
- AE-4: Ratio of cited_claims / total_claims (0.0-1.0)
- AE-5: Average of claim-level scores (supports=1.0, partial=0.5, contradicts=0.0)
- AE-7: Average of claim-level scores (grounded=1.0, partial=0.5, ungrounded=0.0)

**Rationale:** Consistent ratio-based scoring across all evals. AE-5 and AE-7 use LLM judgment to categorize each claim, then average.

### 4. Citation Correctness Verdict Options
**Decision:** AE-5 LLM verdict categories:
- **supports** (1.0): cited paper directly supports claim
- **partially supports** (0.5): partial alignment or conditional support
- **contradicts** (0.0): paper contradicts or refutes claim
- **unrelated** (0.0): paper exists but claim is not mentioned

**Rationale:** Allows nuanced judgment. "Contradicts" and "unrelated" both score 0 but are distinct findings.

### 5. Grounding Check Without Citations
**Decision:** AE-7 checks grounding by sending claim + all paper summaries to LLM.
- Claim may fail AE-5 (wrong citation) but pass AE-7 (content is actually grounded)
- Claim may pass both (correct citation, grounded content)
- Claim may fail both (uncited AND ungrounded)

**Rationale:** Distinguishes citation errors from hallucinations. Helps debug report quality.

### 6. References Section Stripping
**Decision:** Strip References section from report before extracting citations (following AE-6 pattern).
- Avoids double-counting and false matches in reference list formatting
- AE-7 still processes full report since it's checking claim grounding, not citation validity

**Rationale:** Citations in References section are metadata, not claims in the report body.

### 7. Case-Insensitive Column Matching
**Decision:** Both `match_citation_to_table()` and `parse_table()` use case-insensitive column lookups.

**Rationale:** CSV headers can vary (Title vs title, Authors vs authors). Must normalize.

---

## Edge Cases and Risks Identified

### 1. Null/Empty Citations in Claims
**Risk:** Claim extractor may return Claim with citation=None for factual statements.
**Handling:** AE-4 counts as uncited (correct). AE-5 skips (only checks cited claims). AE-7 includes in grounding check.

### 2. Numeric Citations Without Reference List
**Risk:** Report uses `[1]`, `[2]` but no explicit reference numbering in table.
**Handling:** `match_citation_to_table()` returns None for numeric refs (cannot be structurally matched). AE-6 flags as fabricated. AE-5 cannot match → skips or counts as unrelated.
**Recommendation:** Document assumption that numeric refs are ordered by table row.

### 3. Author Name Variations
**Risk:** Citation has "Smith" but table has "Smith, J." or "John Smith".
**Handling:** `match_citation_to_table()` does substring matching (case-insensitive). Works for surnames but may have false negatives on initials.
**Example:** `[Smith, 2021]` matches table row "Smith, John; 2021" (surname substring found).

### 4. Year Parsing Errors in CSV
**Risk:** Table row has year value that's not a valid integer (e.g., "2021-2022", "n.d.").
**Handling:** `parse_table()` raises ValueError if year cannot be parsed.
**Recommendation:** Data validation upstream; evals should not silently ignore bad years.

### 5. LLM Hallucinations in Claim Extraction
**Risk:** `extract_claims()` may return claims that aren't actually in the report.
**Handling:** LLM response is trusted. No validation against original text.
**Recommendation:** Secondary validation could do regex verification (not in MVP).

### 6. Missing Citation Matches in AE-5
**Risk:** Claim has citation but `match_citation_to_table()` returns None (author/year mismatch).
**Handling:** AE-5 should skip this claim (no paper to check) or count as unrelated.
**Decision Needed:** Clarify whether AE-5 should attempt fuzzy title matching or strict author+year.

### 7. Very Long Reports or Large Tables
**Risk:** Grounding check (AE-7) sends claim + all paper summaries to LLM.
- If 30+ papers × abstract length, token cost could be high.
- LLM context limit may be exceeded.

**Handling:** Current design sends full abstracts. No summarization/truncation planned.
**Recommendation:** Add optional paper truncation (e.g., first 500 chars of abstract) if tokens become a concern.

### 8. Report With No Headings
**Risk:** Report has no markdown headings; all content is "unsectioned".
**Handling:** `_parse_sections()` returns `[("unsectioned", full_report)]`. Claim.section will all be "unsectioned".
**Impact:** Findings will have location info only if citation is detected.

### 9. Empty Claims List
**Risk:** LLM returns empty claims list (report has no factual claims).
**Handling:** All evals handle gracefully. AE-4 score = 1.0 (all 0 claims are cited). AE-5 and AE-7 score = 1.0 (all 0 claims are grounded).
**Implication:** Edge case but valid (opinion piece).

---

## API Signatures for Implementation

### AE-4: Citation Completeness

```python
# Module constants
EVAL_NAME = "ae-4"
REQUIRED_ARTIFACTS = ["report"]

def evaluate_citation_completeness(case: CaseData) -> EvalResult:
    """
    Measure the fraction of factual claims that have inline citations.
    
    Args:
        case: Loaded case data with report.
    
    Returns:
        EvalResult with:
        - score: cited_claims / total_claims (0.0 to 1.0)
        - max_score: 1.0
        - passed: True if score == 1.0 (all claims cited)
        - findings: One Finding per uncited claim (severity="warning")
        - reasoning: Summary of counts and percentage
    """
```

### AE-5: Citation Correctness

```python
# Module constants
EVAL_NAME = "ae-5"
REQUIRED_ARTIFACTS = ["report", "table"]

def evaluate_citation_correctness(case: CaseData) -> EvalResult:
    """
    Verify that cited papers actually support the claims made.
    
    Args:
        case: Loaded case data with report and table.
    
    Returns:
        EvalResult with:
        - score: average of claim-level scores (0.0 to 1.0)
        - max_score: 1.0
        - passed: True if average >= 0.9 (or configurable threshold)
        - findings: One Finding per incorrect/unrelated citation
                    (severity="error" for contradicts, "warning" for unrelated/partial)
        - reasoning: Summary of counts and LLM verdict distribution
    """
```

### AE-7: Grounding Check

```python
# Module constants
EVAL_NAME = "ae-7"
REQUIRED_ARTIFACTS = ["report", "table"]

def evaluate_grounding_check(case: CaseData) -> EvalResult:
    """
    Check whether all claims (cited or not) are grounded in source papers.
    
    Args:
        case: Loaded case data with report and table.
    
    Returns:
        EvalResult with:
        - score: average of claim-level grounding scores (0.0 to 1.0)
        - max_score: 1.0
        - passed: True if average >= 0.9 (or configurable threshold)
        - findings: One Finding per ungrounded/partially-grounded claim
                    (severity="error" for ungrounded, "warning" for partial)
        - reasoning: Summary of counts and grounding verdict distribution
    """
```

---

## Test Data Specifics

**case_001/report.md:**
- 350+ lines of well-formed markdown
- Multiple inline citations: `[5]`, `[14]`, `[Smith, 2021]`, etc.
- Section headings: Introduction, Background, Methods, Key Findings, Discussion, Conclusion
- References section at end (can be stripped)
- 30+ papers cited, table.csv has 2520 rows (30 papers with full metadata)

**Intentional Test Cases:**
- Document mentions that one reference is "intentionally uncited" for testing AE-4
- Document mentions intentionally wrong citation for testing AE-5
- (Clarify with product owner if other test cases exist)

---

## Files to Create/Modify

### New Files (Track B Implementation)
1. `/home/ankitkp4056/Documents/Projects/ankitkp4056/ResearchReportEvals/evals/artifact/citation_completeness.py` (AE-4)
2. `/home/ankitkp4056/Documents/Projects/ankitkp4056/ResearchReportEvals/evals/artifact/citation_correctness.py` (AE-5)
3. `/home/ankitkp4056/Documents/Projects/ankitkp4056/ResearchReportEvals/evals/artifact/grounding_check.py` (AE-7)
4. `/home/ankitkp4056/Documents/Projects/ankitkp4056/ResearchReportEvals/tests/test_citation_completeness.py` (unit tests)
5. `/home/ankitkp4056/Documents/Projects/ankitkp4056/ResearchReportEvals/tests/test_citation_correctness.py` (unit tests)
6. `/home/ankitkp4056/Documents/Projects/ankitkp4056/ResearchReportEvals/tests/test_grounding_check.py` (unit tests)

### Modified Files
1. `/home/ankitkp4056/Documents/Projects/ankitkp4056/ResearchReportEvals/evals/run.py`
   - Add imports for three new evals
   - Add three register_eval() calls

### Reference Files (Read-Only, Already Complete)
- `evals/shared/loader.py`
- `evals/shared/results.py`
- `evals/shared/llm_judge.py`
- `evals/shared/claim_extractor.py`
- `evals/shared/citation_parser.py`
- `evals/shared/table_parser.py`
- `evals/artifact/fabricated_references.py` (pattern reference)
- `samples/case_001/*` (test data)

---

## Implementation Checklist

### Per-Eval Implementation
For each of AE-4, AE-5, AE-7:

1. Create module file: `evals/artifact/<eval_name>.py`
2. Define module-level constants: `EVAL_NAME`, `REQUIRED_ARTIFACTS`
3. Implement eval function: `evaluate_<name>(case: CaseData) -> EvalResult`
4. Add standalone `if __name__ == "__main__"` entry point for testing
5. Create corresponding test file: `tests/test_<eval_name>.py`
6. Write unit tests covering:
   - Basic happy path (valid claims, citations, matches)
   - Edge cases (empty claims, null citations, no matches)
   - Score computation correctness
   - Finding generation correctness
7. Update `evals/run.py` to import and register the eval

### Final Validation
1. Run each eval standalone: `python -m evals.artifact.<eval_name> samples/case_001/`
2. Run eval runner: `python -m evals.run samples/case_001/`
3. Verify eval_results.json contains all three eval results
4. Check that findings are sensible for sample data
5. Verify standalone mode and runner mode produce identical results

---

## Summary of Key APIs and Patterns

### Eval Function Signature
All evals follow this pattern:
```python
def evaluate_<name>(case: CaseData) -> EvalResult:
    # 1. Initialize LLMJudge (if needed)
    judge = LLMJudge()
    
    # 2. Extract claims
    claims = extract_claims(case.report, judge)
    
    # 3. Process claims (filter, check citations, send to LLM, etc.)
    findings = []
    scores = []
    for claim in claims:
        # ... eval-specific logic
        pass
    
    # 4. Compute aggregate score
    score = sum(scores) / len(scores) if scores else 1.0
    
    # 5. Build and return EvalResult
    return EvalResult(
        eval_name=EVAL_NAME,
        score=score,
        max_score=1.0,
        passed=score >= 0.9,  # or other threshold
        findings=findings,
        reasoning=f"Checked {len(claims)} claims. Found {len(findings)} issues.",
    )
```

### Common Imports for All Three Evals
```python
from evals.shared.loader import CaseData, load_case
from evals.shared.results import EvalResult, Finding
from evals.shared.llm_judge import LLMJudge
from evals.shared.claim_extractor import extract_claims
from evals.shared.citation_parser import match_citation_to_table
```

### AE-5 and AE-7 Specific
```python
# For AE-5 (correctness checking)
from evals.shared.citation_parser import extract_citations, match_citation_to_table
from evals.shared.table_parser import parse_table

# For AE-7 (grounding checking)
from evals.shared.table_parser import parse_table, PaperRecord
```

---

## Conclusion

Track B implementation is straightforward once the shared infrastructure (loader, llm_judge, claim_extractor, citation_parser, table_parser) is understood. All three evals follow the same structural pattern:

1. Load case
2. Initialize LLMJudge if needed
3. Extract claims
4. Process each claim (filter, match citations, query LLM)
5. Build findings list
6. Compute aggregate score
7. Return EvalResult

The main complexity is in prompt engineering for AE-5 and AE-7 (LLM judgment of correctness/grounding), but the data flow is clear and all supporting utilities are in place and well-documented.
