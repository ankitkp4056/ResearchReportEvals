# Exploration: Foundation — Data + Parsers Sprint

**Date:** 2026-04-03  
**Sprint:** SPRINT_FOUNDATION_PARSERS.md

## Scope Summary

This sprint builds the foundational data layer and pure parsing utilities (no LLM dependency) that all evals depend on. The sprint consists of 4 tasks:

1. **Sample test data** in `samples/case_001/` with 4 artifacts
2. **Artifact loader** (`evals/shared/loader.py`) — loads and validates case folders
3. **Citation parser** (`evals/shared/citation_parser.py`) — extracts and matches citations
4. **Table parser** (`evals/shared/table_parser.py`) — parses CSV table into structured records

All code must conform to exact interface contracts specified in SPRINT_FOUNDATION_PARSERS.md, as downstream sessions (Foundation LLM, Integration, Tracks A/B) depend on these interfaces.

---

## Current State

### What Exists
- Directory structure already in place:
  - `evals/` with subdirectories: `artifact/`, `shared/`, `system/`
  - `samples/` with subdirectories: `case_001/`, `case_002/`, `case_003/`
  - `docs/` with eval strategy and sprint docs
  - `golden/` (empty, for future golden data)

- `samples/case_001/` partially populated:
  - **EXISTS:** `query.txt` — realistic research query about "AI-based early cancer detection methods comparing imaging, genomics, multimodal approaches"
  - **MISSING:** `todo.md`, `table.csv`, `report.md`

- `evals/shared/` is empty (no `.py` files)
- Project has no `requirements.txt`, no `venv/` setup

### Git Status
- Initial commit: `0472e49`
- Main branch is active
- Tracked files: `.claude/`, `docs/`, `evals/` (structure only)
- Untracked: `samples/`, `.gitignore`

---

## Task Breakdown

### Task 1: Sample Test Data

**Objective:** Create realistic but intentionally flawed test data so evals have something to catch.

**Files to create in `samples/case_001/`:**

1. **`todo.md`** — Planning document produced by agent Step 1
   - Should capture research scope from the query (cancer detection methods)
   - Include sections/headings for research areas
   - Focus areas matching the query intent (imaging, genomics, multimodal)
   - Real-looking planning structure (~500 words estimated)

2. **`table.csv`** — Extraction table from agent Step 5
   - **Required columns:** `title`, `authors`, `year`, `DOI`, `abstract`
   - **Focus criteria columns:** 3-4 dynamic columns specific to the research question (e.g., `imaging_method`, `auc_score`, `specificity`)
   - **Data:** ~5 synthetic papers with realistic-looking but fake data
   - **Key constraint:** This is the source of truth for what papers exist in the retrieval set
   - **Intentional imperfection:** At least one paper should be intentionally incomplete (missing abstract or DOI) for error testing

3. **`report.md`** — Generated research report (~1000 words)
   - Include markdown sections and inline citations
   - Purposefully include intentional errors for evals to catch:
     - **1 fabricated reference:** A citation to a paper NOT in the table (e.g., "[Smith et al., 2023]" where Smith is not in table)
     - **1 uncited claim:** A factual claim with no citation
     - **1 wrong citation:** A claim attributed to one paper that actually belongs to another (wrong paper ID)
   - Use realistic academic writing style

**Note:** The existing `query.txt` is about cancer detection with metrics (AUC, sensitivity, specificity). The todo.md, table.csv, and report.md should all be coherent with this query.

---

### Task 2: Artifact Loader

**File:** `evals/shared/loader.py`

**Interface Contract (exact signatures must match):**

```python
@dataclass
class CaseData:
    query: str
    plan: str
    table: list[dict]  # raw CSV rows via DictReader
    report: str
    case_path: Path

def load_case(case_path: str) -> CaseData: ...
```

**Implementation requirements:**

1. `CaseData` dataclass:
   - `query: str` — raw text from query.txt
   - `plan: str` — raw text from todo.md
   - `table: list[dict]` — parsed CSV rows as dictionaries (via `csv.DictReader`)
   - `report: str` — raw text from report.md
   - `case_path: Path` — pathlib.Path object pointing to case folder

2. `load_case(case_path: str) -> CaseData`:
   - Accept string path to case folder (e.g., `"samples/case_001"`)
   - Read all 4 files: `query.txt`, `todo.md`, `table.csv`, `report.md`
   - Validate all files exist; raise clear error if any missing
   - Parse table.csv using `csv.DictReader` — preserve header row names as dict keys
   - Return CaseData instance
   - Error handling: descriptive FileNotFoundError, ValueError for malformed CSV

**Key design notes:**
- Import `from pathlib import Path`
- Use `csv.DictReader` for table parsing — do not parse as PaperRecord yet (that's Task 4's job)
- The loader is the entry point for all evals, so it must be robust

---

### Task 3: Citation Parser

**File:** `evals/shared/citation_parser.py`

**Interface Contract:**

```python
@dataclass
class Citation:
    raw_text: str
    authors: list[str] | None
    year: int | None
    reference_id: str | None

def extract_citations(report: str) -> list[Citation]: ...
def match_citation_to_table(citation: Citation, table: list[dict]) -> dict | None: ...
```

**Implementation requirements:**

1. `Citation` dataclass:
   - `raw_text: str` — the original citation text as it appears in report (e.g., "[Smith et al., 2023]")
   - `authors: list[str] | None` — parsed author list, or None if unparseable
   - `year: int | None` — extracted year as integer, or None
   - `reference_id: str | None` — ID from numbered citations like "[1]", or None

2. `extract_citations(report: str) -> list[Citation]`:
   - Parse report.md for inline citations
   - Support multiple citation formats:
     - `[Author, Year]` or `[Author et al., Year]`
     - `[1]`, `[2]` (numbered references)
     - `(Author, Year)` parenthetical style
     - Footnote-style (if any)
   - Return list of Citation objects in order of appearance
   - Duplicate citations should be preserved as separate entries (or deduplicated? Spec is unclear)

3. `match_citation_to_table(citation: Citation, table: list[dict]) -> dict | None`:
   - Attempt to fuzzy-match a Citation to a row in the table (list of dicts)
   - Use `rapidfuzz` for fuzzy string matching (title, authors, year)
   - Return the matching dict row if found, else None
   - Matching strategy:
     - Try to match authors (if provided) + year (if provided) first
     - Fall back to title-based fuzzy matching if authors/year insufficient
     - Use threshold (suggest 0.8 similarity) to avoid false positives
   - **Edge case:** What if multiple papers match? Return first best match or raise exception?

**Key design notes:**
- Citation extraction is regex-heavy but deterministic (no LLM)
- The spec lists multiple formats but isn't exhaustive — use regex with reasonable heuristics
- Import `from rapidfuzz import fuzz` for fuzzy matching
- This module will be used by AE-6 (Fabricated References eval) and AE-5 (Citation Correctness)

**Ambiguity noted:** The spec doesn't specify behavior for multiple matching papers (e.g., two papers by same author same year). Recommend returning first best match.

---

### Task 4: Table Parser

**File:** `evals/shared/table_parser.py`

**Interface Contract:**

```python
@dataclass
class PaperRecord:
    title: str
    authors: str
    year: int
    doi: str | None
    abstract: str | None
    focus_columns: dict[str, str]

def parse_table(csv_path: str) -> list[PaperRecord]: ...
def get_paper_by_title(table: list[PaperRecord], query: str) -> PaperRecord | None: ...
```

**Implementation requirements:**

1. `PaperRecord` dataclass:
   - `title: str` — paper title (required)
   - `authors: str` — author string as-is from CSV (no parsing; that's Citation's job)
   - `year: int` — publication year as integer
   - `doi: str | None` — DOI if present, else None
   - `abstract: str | None` — abstract text if present, else None
   - `focus_columns: dict[str, str]` — dynamic dict for any columns beyond the standard 5 (title, authors, year, DOI, abstract)

2. `parse_table(csv_path: str) -> list[PaperRecord]`:
   - Read CSV file at given path
   - Auto-detect standard metadata columns: `title`, `authors`, `year`, `DOI`, `abstract`
   - All other columns become focus_columns (e.g., `imaging_method`, `auc_score`, `specificity`)
   - Parse `year` as integer; raise ValueError if non-numeric
   - Return list of PaperRecord objects
   - Error handling: FileNotFoundError, ValueError for malformed year or missing title

3. `get_paper_by_title(table: list[PaperRecord], query: str) -> PaperRecord | None`:
   - Fuzzy-match a title query against papers in table
   - Use `rapidfuzz` with threshold (suggest 0.8)
   - Return first matching PaperRecord, or None if no match
   - Case-insensitive matching

**Key design notes:**
- Standard columns: title, authors, year, DOI, abstract (case-insensitive on CSV headers)
- Focus columns: any other columns in the CSV
- Import `from rapidfuzz import fuzz`
- Year parsing: must be integer, not string

**Ambiguity noted:** Column names in CSV may vary in case (e.g., "Title" vs "title"). Recommend normalizing to lowercase for matching.

---

## Dependencies & Integration Points

### Dependencies within Sprint
- Task 2 (loader) depends on Tasks 1 (data must exist)
- Task 3 (citation parser) is independent
- Task 4 (table parser) is independent
- Tasks 3 & 4 will be used together in Task 5 (Integration sprint)

### Dependencies on Other Sprints
- **No blocking dependencies** — this sprint is isolated (stated: "This session runs in parallel with SPRINT_FOUNDATION_LLM.md — no cross-dependencies")
- **Will be used by:**
  - Foundation LLM sprint: needs sample data to test claim extractor
  - Foundation Integration sprint: needs all 4 modules to build AE-6 eval
  - All downstream eval tracks (A, B): depend on loader

### Integration with Eval Strategy
- Citation parser used by:
  - AE-6 (Fabricated References) — detect citations not in table
  - AE-5 (Citation Correctness) — match claims to papers
  - AE-4 (Citation Completeness) — count cited vs uncited claims

- Table parser used by:
  - AE-6 (Fabricated References) — list of valid papers
  - AE-5 (Citation Correctness) — source paper lookup
  - AE-4 & AE-7 — need paper abstracts/content

- Loader used by:
  - All evals in artifact/ and system/ — entry point for every eval

---

## Naming Constraints & Conventions

**Module names must match exactly:**
- `evals/shared/loader.py` (not `artifact_loader.py` or `case_loader.py`)
- `evals/shared/citation_parser.py` (not `citations.py` or `ref_parser.py`)
- `evals/shared/table_parser.py` (not `paper_parser.py` or `table_reader.py`)

**Class names must match exactly:**
- `CaseData`, `Citation`, `PaperRecord` (PascalCase as shown)
- `Finding`, `EvalResult` (in LLM sprint, but imported by this sprint's tests)

**Function names must match exactly:**
- `load_case()`, `extract_citations()`, `match_citation_to_table()`, `parse_table()`, `get_paper_by_title()`

**Dataclass fields must match exactly:**
- CaseData: `query`, `plan`, `table`, `report`, `case_path`
- Citation: `raw_text`, `authors`, `year`, `reference_id`
- PaperRecord: `title`, `authors`, `year`, `doi`, `abstract`, `focus_columns`

---

## Key Decisions & Resolved Ambiguities

### Resolved
1. **Table format:** CSV using `csv.DictReader` (preserves column names)
2. **Focus columns:** Any column not in {title, authors, year, DOI, abstract}
3. **Citation parsing:** Regex-based, supports multiple formats
4. **Fuzzy matching threshold:** Recommend 0.8 (not specified; may need tuning)

### Remaining Ambiguities
1. **Citation deduplication:** Should `extract_citations()` deduplicate citations by `(authors, year)` or preserve all instances? 
   - Spec doesn't clarify. Impact: affects count and order.
   - **Recommendation:** Preserve all instances (order matters for report flow)

2. **Multiple paper matches:** What if fuzzy matching finds multiple papers above threshold?
   - Spec doesn't clarify. 
   - **Recommendation:** Return first best match (sorted by score descending)

3. **Citation format edge cases:** What about:
   - Nested citations: "[see Smith et al. (2023) and Jones (2021)]"?
   - URLs as citations: "[https://arxiv.org/...]"?
   - Author-only citations: "[Smith]" without year?
   - **Recommendation:** Handle basic formats; log/skip edge cases

4. **Year parsing:** What if CSV has year as "2023-2024" or non-numeric text?
   - Spec says parse as int, but doesn't specify error behavior.
   - **Recommendation:** Raise ValueError with clear message; skip papers with bad years

5. **Column name case sensitivity:** "Title" vs "title" vs "TITLE"?
   - **Recommendation:** Normalize to lowercase before checking

6. **Focus columns naming:** Can focus columns have names that conflict? (e.g., "title_relevance")
   - **Recommendation:** Allow any name; parser distinguishes by column position, not name uniqueness

---

## Edge Cases & Risks

### High Priority
- **Missing files in case folder:** Loader must handle gracefully and fail with clear error
- **Malformed CSV:** Missing headers, ragged rows, non-numeric year — catch and report
- **No citations in report:** `extract_citations()` should return empty list (not error)
- **Empty table:** `parse_table()` should handle empty CSV (return empty list or raise?)
  - **Recommendation:** Return empty list (consistent with no-matches for other parsers)

### Medium Priority
- **Fabricated citation in report:** Must be detected by citation parser (intentional test case)
- **Fuzzy matching false positives:** E.g., matching "Smith 2023" to wrong "Smith et al. 2023"
  - **Mitigation:** Use threshold tuning and manual testing
- **Unicode/special characters in titles:** Regex may choke on non-ASCII
  - **Mitigation:** Test with diverse author names

### Low Priority (but noted)
- **Very long report:** Regex citation extraction may be slow on 50+ page PDFs
  - Unlikely for evals (reports ~1000 words per spec)
- **CSV encoding:** If table.csv has non-UTF8 encoding, DictReader may fail
  - **Mitigation:** Document expected encoding; can add encoding param if needed

---

## File Structure After Completion

```
ResearchReportEvals/
├── samples/
│   └── case_001/
│       ├── query.txt                    [EXISTS - cancer detection query]
│       ├── todo.md                      [TO CREATE]
│       ├── table.csv                    [TO CREATE - ~5 papers + focus cols]
│       └── report.md                    [TO CREATE - ~1000 words with intentional errors]
├── evals/
│   ├── shared/
│   │   ├── __init__.py                  [TO CREATE in Integration sprint]
│   │   ├── loader.py                    [TO CREATE - CaseData, load_case()]
│   │   ├── citation_parser.py           [TO CREATE - Citation, extract_citations(), match_citation_to_table()]
│   │   └── table_parser.py              [TO CREATE - PaperRecord, parse_table(), get_paper_by_title()]
│   ├── artifact/
│   └── system/
├── docs/
│   ├── EVAL_STRATEGY.md
│   ├── SPRINT_FOUNDATION_PARSERS.md
│   ├── SPRINT_FOUNDATION_LLM.md
│   ├── SPRINT_FOUNDATION_INTEGRATION.md
│   ├── SPRINT_TRACK_A.md
│   ├── SPRINT_TRACK_B.md
│   └── EXPLORE_FOUNDATION_PARSERS.md     [THIS FILE]
└── requirements.txt                      [TO CREATE in Integration sprint]
```

---

## Test Strategy

All modules should be testable independently:

```bash
# After completion, these should work:
python -c "from evals.shared.loader import load_case, CaseData; cd = load_case('samples/case_001')"
python -c "from evals.shared.citation_parser import extract_citations; cits = extract_citations(open('samples/case_001/report.md').read())"
python -c "from evals.shared.table_parser import parse_table; papers = parse_table('samples/case_001/table.csv')"
```

The Integration sprint will create the eval runner and AE-6 to validate end-to-end:

```bash
python -m evals.run samples/case_001/  # After Integration sprint
```

Expected: AE-6 should detect the 1 fabricated reference planted in report.md.

---

## Open Questions for Clarification

1. **Citation deduplication:** Should identical citations appearing multiple times in a report be deduplicated or preserved?

2. **Multiple fuzzy matches:** When fuzzy matching finds multiple papers above threshold, should we:
   - Return the single best match?
   - Return all matches?
   - Raise an ambiguity error?

3. **CSV header normalization:** Should column names be normalized to lowercase? What if user provides "Title" vs "title"?

4. **Empty CSV handling:** Should `parse_table()` on an empty CSV return `[]` or raise an error?

5. **Year validation:** For non-numeric year in table.csv, should we:
   - Raise ValueError immediately?
   - Skip that row with warning?
   - Try to parse (e.g., "2023-2024" → 2023)?

6. **Citation format scope:** Which citation formats are "in scope" for extraction? The spec lists ~5 formats but is there a canonical list?

7. **DOI normalization:** Should DOI be normalized (e.g., remove "https://doi.org/" prefix) or stored as-is?

---

## Conclusion

The sprint is well-specified with exact interface contracts. The main implementation work is:

1. **Test data (Task 1):** Create realistic but imperfect sample case with intentional errors
2. **Loader (Task 2):** Straightforward file I/O + CSV parsing with validation
3. **Citation parser (Task 3):** Regex-based extraction + fuzzy matching to table
4. **Table parser (Task 4):** CSV parsing + dynamic focus columns + fuzzy title lookup

All modules are pure Python with no LLM or external API calls. Dependencies: `csv` (stdlib), `pathlib` (stdlib), `rapidfuzz` (external, for fuzzy matching).

The sprint is independent of the concurrent LLM sprint but will be integrated in the Foundation Integration sprint.

No blockers identified; ready to proceed once open questions above are clarified.
