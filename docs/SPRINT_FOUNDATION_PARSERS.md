# Sprint: Foundation — Data + Parsers

**Overall Progress:** `0%`

## TLDR
Build sample test data and all pure parsing utilities (no LLM dependency). These are the data layer that other foundation sessions and all evals depend on.

## Context
- Eval strategy: `docs/EVAL_STRATEGY.md`
- Each case lives in `samples/case_NNN/` with: `query.txt`, `todo.md`, `table.csv`, `report.md`
- All shared code goes in `evals/shared/`
- Python 3.11+, type hints encouraged
- This session runs in parallel with `SPRINT_FOUNDATION_LLM.md` — no cross-dependencies

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

- [ ] 🟥 **Task 1: Sample test data**
  - [ ] 🟥 Create `samples/case_001/query.txt` — a realistic research query (e.g., "Compare effectiveness of CBT vs DBT for treatment-resistant depression")
  - [ ] 🟥 Create `samples/case_001/todo.md` — a realistic planning doc with research scope, headings, focus areas matching the query
  - [ ] 🟥 Create `samples/case_001/table.csv` — realistic extraction table with ~5 papers, columns: title, authors, year, DOI, abstract, and 3-4 focus criteria columns. Include real-looking but synthetic paper data
  - [ ] 🟥 Create `samples/case_001/report.md` — realistic research report (~1000 words) with inline citations referencing papers from table.csv. Intentionally include: 1 fabricated reference (not in table), 1 uncited claim, 1 claim with wrong citation — so evals have something to catch

- [ ] 🟥 **Task 2: Artifact loader** (`evals/shared/loader.py`)
  - [ ] 🟥 `load_case(case_path: str) -> CaseData` — reads case folder, validates all 4 artifacts exist
  - [ ] 🟥 `CaseData` dataclass with fields: `query: str`, `plan: str`, `table: list[dict]` (parsed CSV rows), `report: str`, `case_path: Path`
  - [ ] 🟥 Parse table.csv into list of dicts using csv.DictReader
  - [ ] 🟥 Raise clear errors if files are missing or malformed

- [ ] 🟥 **Task 3: Citation parser** (`evals/shared/citation_parser.py`)
  - [ ] 🟥 `extract_citations(report: str) -> list[Citation]` — parse all inline citations from report markdown
  - [ ] 🟥 Handle common citation formats: `[Author, Year]`, `[1]`, `(Author et al., Year)`, footnote-style
  - [ ] 🟥 `Citation` dataclass: `raw_text: str`, `authors: list[str] | None`, `year: int | None`, `reference_id: str | None`
  - [ ] 🟥 `match_citation_to_table(citation: Citation, table: list[dict]) -> dict | None` — fuzzy match a citation to a table.csv row by author/title/year

- [ ] 🟥 **Task 4: Table parser** (`evals/shared/table_parser.py`)
  - [ ] 🟥 `parse_table(csv_path: str) -> list[PaperRecord]` — parse table.csv into structured records
  - [ ] 🟥 `PaperRecord` dataclass: `title: str`, `authors: str`, `year: int`, `doi: str | None`, `abstract: str | None`, plus dynamic `focus_columns: dict[str, str]` for any extra columns
  - [ ] 🟥 Auto-detect which columns are metadata vs focus criteria (metadata = title, authors, year, DOI, abstract; rest = focus criteria)
  - [ ] 🟥 `get_paper_by_title(table: list[PaperRecord], query: str) -> PaperRecord | None` — fuzzy title match
