# Exploration: Foundation Integration Sprint

**Sprint:** `SPRINT_FOUNDATION_INTEGRATION.md`  
**Date:** 2025-04-03

---

## Scope Summary

This sprint integrates the Foundation Parsers and Foundation LLM subsystems into a working evaluation pipeline. The key tasks are:

1. **Package init files** — export core classes from evals modules
2. **Eval runner + CLI** — registry-based runner with selective execution
3. **AE-6 eval** — fabricated references detection (integration test)
4. **requirements.txt** — add openai, rapidfuzz
5. **End-to-end validation** — run AE-6 on sample data

All prerequisites are complete: `loader.py`, `citation_parser.py`, `table_parser.py`, `llm_judge.py`, `claim_extractor.py`, and `results.py` are all implemented.

---

## Relevant Existing Files and Their Roles

### Core Modules (evals/shared/)

| File | Key Classes/Functions | Purpose |
|------|----------------------|---------|
| `loader.py` | `CaseData`, `load_case()` | Load case directory into structured object |
| `citation_parser.py` | `Citation`, `extract_citations()`, `match_citation_to_table()` | Extract and match citations |
| `table_parser.py` | `PaperRecord`, `parse_table()`, `get_paper_by_title()` | Parse CSV table into structured records |
| `results.py` | `Finding`, `EvalResult`, `CaseResults` | Result schema with JSON serialization |
| `llm_judge.py` | `LLMJudge` class | OpenAI-compatible LLM wrapper with JSON parsing |
| `claim_extractor.py` | `Claim`, `extract_claims()` | Extract factual claims from report via LLM |

### Package Init Files (Current State)

- `evals/__init__.py` — minimal stub (one line comment)
- `evals/shared/__init__.py` — minimal stub (one line comment)
- `evals/artifact/__init__.py` — minimal stub (one line comment)
- `evals/system/__init__.py` — minimal stub (one line comment)

**Action:** Task 1 requires exporting key classes from `evals/shared/__init__.py`:
- `CaseData`, `LLMJudge`, `EvalResult`, `CaseResults`, `Citation`, `Claim`, `PaperRecord`

### Test Suite

Located in `tests/`:
- `test_results.py` — validates Finding, EvalResult, CaseResults serialization
- `test_llm_judge.py` — tests LLMJudge with mock responses
- `test_claim_extractor.py` — tests claim extraction logic

Tests reference `fabricated_references` as an eval name (line 98 of test_results.py), confirming it's an expected eval.

### Sample Data (samples/case_001/)

| File | Size | Contents |
|------|------|----------|
| `query.txt` | - | Raw user query |
| `todo.md` | - | Planning doc |
| `table.csv` | 2521 lines | 30 reference papers (first 30 rows; 98 total rows with additional metadata) |
| `report.md` | ~350 lines | Research report on AI-based cancer detection |

**Key Finding:** The report contains 30 numeric citations `[1]` through `[30]`, corresponding to the 30 reference papers in the table.

### Requirements

**Current requirements.txt:**
```
openai>=1.0.0
pytest>=7.0.0
```

**Missing:** `rapidfuzz` (for fuzzy matching in citation/table parsing). Task 4 adds both `openai` and `rapidfuzz` with pinned versions.

---

## Dependencies and Integration Points

### Data Flow

```
samples/case_001/ (directory)
    ├── query.txt
    ├── todo.md
    ├── table.csv
    └── report.md
            ↓
    load_case() → CaseData
            ↓
    extract_citations(report) → list[Citation]
    parse_table(table.csv) → list[PaperRecord]
            ↓
    match_citation_to_table(citation, table) → PaperRecord | None
            ↓
    For unmatched citations:
        EvalResult(fabricated_references, score=0.0, findings=[...])
            ↓
    CaseResults.save() → eval_results.json
```

### AE-6 (Fabricated References) Eval

**Purpose:** Detect citations in report that don't match any paper in the extraction table.

**Logic:**
1. Load case with `load_case()`
2. Extract citations from report with `extract_citations()`
3. Extract paper list from table (use raw `CaseData.table` or `parse_table()`)
4. For each citation, attempt `match_citation_to_table()`
5. Flag unmatched citations as severity="error" findings
6. Return `EvalResult` with:
   - `score=1.0` if all citations matched, else `0.0`
   - `max_score=1.0`
   - `passed=True` if score == 1.0
   - `findings` listing each unmatched citation

**Integration:** Must register with the eval runner (Task 2).

### Eval Runner (evals/run.py)

**Purpose:** Discover, run, and aggregate evals for a case.

**Key Components:**
- **Registry:** Maps eval name (e.g., "ae-6", "ae-1") to eval function and required artifacts
- **Runner:** Calls `load_case()`, checks required artifacts, runs applicable evals, catches errors
- **CLI:** `python -m evals.run samples/case_001/` with optional `--only ae-6,ae-1` flag
- **Output:** Prints summary table to terminal, writes `eval_results.json` to case folder

**Registry Design:**
```python
EVAL_REGISTRY = {
    "ae-6": {
        "fn": evaluate_fabricated_references,
        "required_artifacts": ["report", "table"],
    },
    # "ae-1": ... (future evals)
}
```

**Error Handling:** If one eval fails, log error and continue with remaining evals.

---

## Fabricated Reference in Sample Data

**Discovery:**

The sample data contains **one intentional fabricated reference** for testing purposes.

**Identification:**

Reference `[6]` (Tanaka et al., "The current issues...") appears in the References section of report.md but is **never cited in the report body**. It does not appear in any inline citations (search for `[6]` in body sections returns no results before the References section).

**Table Coverage:**

The table has:
- First 30 rows = the 30 papers cited in the report (references [1]–[30])
- Rows 31-98 = additional metadata or supplementary papers

When AE-6 runs on this data:
- It will extract 30 numeric citations `[1]` through `[30]` from the report body
- It will attempt to match each numeric citation to the table
- All 30 citations should match the first 30 rows
- **Reference [6]** appears in the References section but is **not inline-cited**, so a more sophisticated eval (checking if all references are used) would catch it

**Note for Implementation:**

The current AE-6 design (matching inline citations to table) will pass this sample because all inline citations ARE in the table. To catch the fabricated reference, a future enhanced AE-6 or a different eval (AE-7: "Unused References") would need to:
1. Parse the reference list from the report footer
2. Check if each reference is actually cited in the body
3. Flag uncited references as fabricated

**Current AE-6 will:**
- Extract [1]–[30] from body citations
- Match them all successfully to table rows 1–30
- Return score=1.0, passed=True

This is correct behavior for the pure "citation match" eval. The planted fake is designed to catch a more sophisticated eval.

---

## Key Decisions and Ambiguities Resolved

### 1. Citation Matching Strategy

**Decision:** Use numeric references for matching.

**Reasoning:**
- The sample uses numeric citations `[1]–[30]`
- Numeric citations cannot be resolved structurally (no author/year in the `[5]` format)
- AE-6 maps citations by their numeric index to table row position

**Implementation:**
- For numeric refs `[N]`, assume table row (N-1) corresponds to reference N
- This assumes the first 30 rows of the table are the 30 cited papers in order

### 2. Table Structure

**Decision:** Use raw `CaseData.table` (list[dict]) for matching, not parsed `PaperRecord` objects.

**Reasoning:**
- `CaseData.table` preserves original column names (easier case-insensitive lookup)
- `parse_table()` is stricter and raises on missing required columns
- AE-6 is a pure script eval (no LLM), so raw CSV works fine

**Alternative:** Could use `parse_table()` if table structure is validated upstream.

### 3. Error Handling in Runner

**Decision:** Catch eval exceptions, log them, and continue.

**Reasoning:**
- One failing eval should not block others
- Errors should be recorded but not fatal
- User gets partial results with error details

### 4. Export Scope

**Task 1 exports from evals/shared/__init__.py:**

Classes to export:
- `CaseData` (from loader.py)
- `LLMJudge` (from llm_judge.py)
- `EvalResult` (from results.py)
- `CaseResults` (from results.py)
- `Citation` (from citation_parser.py)
- `Claim` (from claim_extractor.py)
- `PaperRecord` (from table_parser.py)

This allows downstream code to do:
```python
from evals.shared import CaseData, LLMJudge, EvalResult, ...
```

---

## Edge Cases and Risks

### 1. Numeric Citation Indexing

**Risk:** If table rows are not in the same order as references, numeric matching fails.

**Mitigation:**
- Document assumption clearly
- Add validation in runner: assert len(table) >= max(citation_ids)

### 2. Case-Insensitive Column Lookup

**Risk:** `match_citation_to_table()` uses case-insensitive lookups for "Authors" and "Year" columns. If table headers are corrupted, matching fails silently.

**Mitigation:**
- `load_case()` already validates CSV has header row
- `citation_parser.py` handles missing columns gracefully (returns None)

### 3. Missing Required Artifacts

**Risk:** If report.md or table.csv is missing, AE-6 should skip silently (not crash).

**Mitigation:**
- Runner checks required artifacts before running eval
- load_case() raises FileNotFoundError if artifacts missing — runner should catch this

### 4. Empty or Malformed Citations

**Risk:** `extract_citations()` might extract malformed citation strings.

**Mitigation:**
- `extract_citations()` returns validated Citation objects
- Regex patterns are well-tested (from citation_parser tests)

### 5. Performance on Large Tables

**Risk:** Table has 98 rows; matching 30 citations against all rows is O(30*98) with string comparisons.

**Mitigation:**
- Not a bottleneck for current scale
- Could optimize with rapidfuzz in future (Task 4 adds it)

### 6. JSON Serialization

**Risk:** `CaseResults.save()` must handle asdict() conversion cleanly.

**Mitigation:**
- `results.py` already tested (test_results.py)
- Finding, EvalResult are dataclasses with standard types

---

## Implementation Notes for Downstream Tasks

### Task 1: Package Init Files

Export these 7 classes from `evals/shared/__init__.py`:

```python
from evals.shared.loader import CaseData
from evals.shared.llm_judge import LLMJudge
from evals.shared.results import EvalResult, CaseResults
from evals.shared.citation_parser import Citation
from evals.shared.claim_extractor import Claim
from evals.shared.table_parser import PaperRecord

__all__ = [
    "CaseData",
    "LLMJudge",
    "EvalResult",
    "CaseResults",
    "Citation",
    "Claim",
    "PaperRecord",
]
```

### Task 2: Eval Runner

Create `evals/run.py` with:
- `EVAL_REGISTRY` dict
- `runner(case_path: str, only: list[str] | None)` function
- `main()` with argparse for CLI
- Summary table printer

### Task 3: AE-6 Eval

Create `evals/artifact/fabricated_references.py`:
```python
def evaluate_fabricated_references(case: CaseData) -> EvalResult:
    citations = extract_citations(case.report)
    findings = []
    for cit in citations:
        if match_citation_to_table(cit, case.table) is None:
            findings.append(Finding(
                severity="error",
                message=f"Citation not found in table: {cit.raw_text}",
                location=None,
            ))
    score = 1.0 if not findings else 0.0
    return EvalResult(
        eval_name="ae-6",
        score=score,
        max_score=1.0,
        passed=(score == 1.0),
        findings=findings,
    )
```

Then register in runner:
```python
EVAL_REGISTRY["ae-6"] = {
    "fn": evaluate_fabricated_references,
    "required_artifacts": ["report", "table"],
}
```

### Task 4: requirements.txt

Add:
```
openai>=1.0.0
rapidfuzz>=3.0.0
pytest>=7.0.0
```

### Task 5: End-to-End Validation

Run:
```bash
python -m evals.run samples/case_001/
```

Verify:
1. AE-6 runs successfully
2. Output table shows ae-6: score=1.0, passed=True
3. `samples/case_001/eval_results.json` exists with correct structure

---

## Summary Table

| Component | Status | Exports/Key Classes | Notes |
|-----------|--------|-------------------|-------|
| loader.py | ✅ Complete | CaseData, load_case() | Ready to use |
| citation_parser.py | ✅ Complete | Citation, extract_citations(), match_citation_to_table() | Ready to use |
| table_parser.py | ✅ Complete | PaperRecord, parse_table(), get_paper_by_title() | Ready to use |
| results.py | ✅ Complete | Finding, EvalResult, CaseResults | Ready to use |
| llm_judge.py | ✅ Complete | LLMJudge class | Requires env vars |
| claim_extractor.py | ✅ Complete | Claim, extract_claims() | Requires LLMJudge |
| evals/__init__.py | ❌ Stub | - | Task 1 |
| evals/shared/__init__.py | ❌ Stub | - | Task 1: export 7 classes |
| evals/artifact/__init__.py | ❌ Stub | - | Task 1 |
| evals/system/__init__.py | ❌ Stub | - | Task 1 |
| evals/run.py | ❌ Missing | Registry, Runner, CLI | Task 2 |
| evals/artifact/fabricated_references.py | ❌ Missing | evaluate_fabricated_references() | Task 3 |
| requirements.txt | ⚠️ Partial | openai, pytest | Task 4: add rapidfuzz |
| sample data | ✅ Complete | report.md, table.csv | Contains 1 fabricated ref |

