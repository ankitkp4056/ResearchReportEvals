# Sprint: Foundation -- Data + Parsers

**Overall Progress:** `100%`

## TLDR
Build sample test data and all pure parsing utilities (no LLM dependency). These are the data layer that other foundation sessions and all evals depend on.

## Exploration Summary

**Current state:** The worktree has no `samples/` or `evals/` directories yet. The main repo has a single `samples/case_001/query.txt` with an unrelated topic (cancer detection). Everything in this sprint is greenfield.

**Key files to create:**
- `samples/case_001/` -- four artifacts (query.txt, todo.md, table.csv, report.md)
- `evals/shared/loader.py` -- case loader
- `evals/shared/citation_parser.py` -- citation extraction and matching
- `evals/shared/table_parser.py` -- CSV to structured records
- `evals/__init__.py`, `evals/shared/__init__.py` -- package init files

**Dependencies:** Only stdlib (`csv`, `re`, `dataclasses`, `pathlib`). The fuzzy matching in `get_paper_by_title` and `match_citation_to_table` can use `difflib.SequenceMatcher` (stdlib) to avoid pulling in `thefuzz`/`rapidfuzz` at this stage. No external packages needed for this sprint.

**Integration points:** The three parser modules are consumed by Phase 1b (integration sprint) which builds AE-6 (Fabricated References) and the eval runner. The exact interfaces are locked in the contract below and must not deviate.

**Risks and edge cases:**
- CSV files may have inconsistent column naming (e.g., "DOI" vs "doi" vs "Doi"). The table parser must normalize column names via case-insensitive matching.
- Citation formats in reports vary widely. The sample report should use a consistent primary format (Author, Year) but the parser must handle at least three formats for robustness.
- Fuzzy matching threshold needs a sensible default (0.6 ratio) but should be tunable.

## Critical Decisions

- Decision 1: Use only stdlib for fuzzy matching (`difflib.SequenceMatcher`) -- avoids adding external dependencies for this foundation layer. Can swap in `thefuzz` later if precision is insufficient.
- Decision 2: Column name detection in table_parser uses a fixed metadata set (`title`, `authors`, `year`, `doi`, `abstract`) with case-insensitive matching -- all other columns become `focus_columns`.
- Decision 3: The sample report uses `(Author, Year)` as the primary citation format, with one `[N]` numeric reference for the fabricated citation -- this exercises multiple parser code paths.
- Decision 4: Sample data uses the CBT vs DBT topic per sprint spec, replacing the cancer detection query in main repo's case_001.

## Interfaces Contract
Other sessions depend on these exact interfaces. Do not deviate.

```python
# evals/shared/loader.py
@dataclass
class CaseData:
    query: str
    plan: str
    table: list[dict]  # raw CSV rows via DictReader
    report: str
    case_path: Path

def load_case(case_path: str) -> CaseData: ...

# evals/shared/table_parser.py
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

# evals/shared/citation_parser.py
@dataclass
class Citation:
    raw_text: str
    authors: list[str] | None
    year: int | None
    reference_id: str | None

def extract_citations(report: str) -> list[Citation]: ...
def match_citation_to_table(citation: Citation, table: list[dict]) -> dict | None: ...
```

## Tasks

- [x] **Task 1: Sample test data**
  - [x] 1.1 Create `samples/case_001/query.txt` -- research query: "Compare effectiveness of CBT vs DBT for treatment-resistant depression, focusing on remission rates, dropout rates, and long-term outcomes"
  - [x] 1.2 Create `samples/case_001/todo.md` -- planning doc with sections: background on treatment-resistant depression, CBT mechanisms and evidence, DBT mechanisms and evidence, head-to-head comparisons, dropout/adherence, long-term follow-up, limitations
  - [x] 1.3 Create `samples/case_001/table.csv` -- 5 synthetic papers with columns: Title, Authors, Year, DOI, Abstract, Remission Rate, Dropout Rate, Follow-up Duration, Sample Size. Papers should span 2018-2023 with plausible synthetic data
  - [x] 1.4 Create `samples/case_001/report.md` -- ~1000-word research report with inline citations in `(Author, Year)` format referencing the 5 table papers. Must intentionally contain these three defects for eval testing:
    - **Fabricated reference:** One citation to a paper NOT in table.csv (e.g., "[7]" numeric style referencing "Martinez & Chen, 2022" which does not exist in the table)
    - **Uncited claim:** One factual/statistical claim with no citation at all (e.g., a sentence stating a specific remission percentage without attribution)
    - **Wrong citation:** One claim attributed to the wrong paper from the table (e.g., citing Paper A's results but attributing them to Paper B)
  - Implementation notes:
    - Mark each intentional defect with an HTML comment (`<!-- DEFECT: ... -->`) so tests can locate them programmatically
    - Keep DOIs in `10.xxxx/xxxxx` format (synthetic but structurally valid)
    - Abstracts in table.csv should be 1-2 sentences each (enough for citation correctness evals to work against)

- [x] **Task 2: Artifact loader** (`evals/shared/loader.py`)
  - [x] 2.1 Create `evals/__init__.py` and `evals/shared/__init__.py` (empty package inits)
  - [x] 2.2 Implement `CaseData` dataclass exactly matching the contract
  - [x] 2.3 Implement `load_case(case_path: str) -> CaseData`:
    - Accept string path, convert to `Path`
    - Validate directory exists
    - Read `query.txt`, `todo.md`, `report.md` as UTF-8 strings
    - Parse `table.csv` via `csv.DictReader` into `list[dict]`
    - Raise `FileNotFoundError` with descriptive message if any of the 4 files missing
    - Raise `ValueError` if CSV is empty or has no header row
  - Implementation notes:
    - Use `pathlib.Path` throughout
    - Strip trailing whitespace from text files
    - CSV parsing: open with `newline=""` per Python csv module docs

- [x] **Task 3: Table parser** (`evals/shared/table_parser.py`)
  - [x] 3.1 Implement `PaperRecord` dataclass exactly matching the contract
  - [x] 3.2 Implement `parse_table(csv_path: str) -> list[PaperRecord]`:
    - Read CSV via `csv.DictReader`
    - Normalize column names: strip whitespace, lowercase for matching against metadata set
    - Metadata columns (case-insensitive match): `title`, `authors`, `year`, `doi`, `abstract`
    - All other columns become keys in `focus_columns` dict (preserve original column names as keys)
    - Convert `year` to `int`; set `doi` and `abstract` to `None` if empty string
    - Raise `ValueError` if `title`, `authors`, or `year` columns are missing
  - [x] 3.3 Implement `get_paper_by_title(table: list[PaperRecord], query: str) -> PaperRecord | None`:
    - Use `difflib.SequenceMatcher` for fuzzy matching
    - Return best match if ratio >= 0.6, else `None`
    - Comparison should be case-insensitive
  - Implementation notes:
    - The 0.6 threshold is a starting default; if integration tests show it is too loose or strict, adjust in Phase 1b
    - Handle potential `ValueError` on `int(year)` gracefully -- raise with context about which row failed

- [x] **Task 4: Citation parser** (`evals/shared/citation_parser.py`)
  - [x] 4.1 Implement `Citation` dataclass exactly matching the contract
  - [x] 4.2 Implement `extract_citations(report: str) -> list[Citation]`:
    - Parse three citation formats using regex:
      - Parenthetical: `(Author et al., 2023)` or `(Author & Author, 2023)` or `(Author, 2023)`
      - Bracket-author: `[Author et al., 2023]` or `[Author, 2023]`
      - Numeric: `[1]`, `[2]`, `[7]`
    - For author-year formats: extract author list and year into Citation fields
    - For numeric formats: set `reference_id` to the number string, authors and year to `None`
    - Deduplicate citations (same raw_text should appear only once in results)
    - Return list ordered by first appearance in text
  - [x] 4.3 Implement `match_citation_to_table(citation: Citation, table: list[dict]) -> dict | None`:
    - Match strategy depends on citation type:
      - If citation has authors + year: match against table rows by last-name substring in "Authors" column AND year match
      - If citation has reference_id only (numeric): return `None` (numeric refs cannot be matched without a reference list)
    - Table rows are raw `list[dict]` from `csv.DictReader` (not PaperRecord) -- use case-insensitive key lookup for "Authors", "Year" columns
    - Return the matching row dict or `None`
  - Implementation notes:
    - Regex patterns should handle "et al." with and without the period
    - Author extraction: split on "&" and "," to get individual names; store last names only in the authors list
    - The match function handles the raw dict format (not PaperRecord) because it is called from eval code that works with the loader's `table: list[dict]` field directly
    - Edge case: multiple table rows could match the same author+year -- return the first match (this is acceptable for the foundation layer; downstream evals can refine)
