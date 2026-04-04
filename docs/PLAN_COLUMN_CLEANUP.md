# Plan: Column & Data Cleanup for Evals

**Status:** Planning (no code changes yet)

---

## Background

The actual `samples/case_001/table.csv` (2,521 rows, 25 columns) uses different column names than what the parsers were built for. This causes hard script crashes in two places. Separately, 17 noise columns inflate LLM prompts with useless tokens — but the LLM handles them fine, so that's a cost optimization, not a correctness fix.

### Impact by Eval

| Eval | Status | Issue |
|------|--------|-------|
| AE-1 (Planning Faithfulness) | OK | — |
| AE-2 (Section Coverage) | OK | Minor prompt design note (see P2) |
| AE-3 (Analysis Depth) | OK | — |
| AE-4 (Citation Completeness) | OK | — |
| AE-5 (Citation Correctness) | **BROKEN** | `table_parser` crashes on column names |
| AE-6 (Fabricated References) | **Partial** | Numeric citations work; author-year matching silently fails |
| AE-7 (Grounding Check) | **BROKEN** | `table_parser` crashes on column names |

---

## P1: Hard Breaks (must fix before any eval runs)

### P1-A: Column Name Mismatch in `table_parser.py`

**File:** `evals/shared/table_parser.py:28`

`_METADATA_COLUMNS` expects exact lowercase names. The CSV uses different names.

```
Expected (metadata set)     Actual CSV Header         Match?
───────────────────────     ─────────────────         ──────
title                       Paper Title               NO
authors                     Author Names              NO
year                        Publication Year          NO
doi                         DOI                       YES
abstract                    Abstract                  YES
```

**Result:** `parse_table()` raises `ValueError: CSV is missing required columns: authors, title, year` — hard crash before any eval logic runs.

**Fix:** Replace `_METADATA_COLUMNS` frozenset with an alias map:

```python
_METADATA_ALIASES: dict[str, list[str]] = {
    "title":    ["title", "paper title"],
    "authors":  ["authors", "author names"],
    "year":     ["year", "publication year"],
    "doi":      ["doi"],
    "abstract": ["abstract"],
}
```

Resolution: for each metadata field, scan CSV headers (lowercased) against alias list. First match wins. Everything unmatched becomes a focus column.

**Files:** `evals/shared/table_parser.py`

---

### P1-B: Column Lookup Bug in `citation_parser.py`

**File:** `evals/shared/citation_parser.py:223-228`

`match_citation_to_table()` calls `_get_col_ci(row, "authors")` which does exact lowercase key comparison. The raw dict from `csv.DictReader` has key `"Author Names"` → lowercased `"author names"` ≠ `"authors"`. Same for `"year"` vs `"publication year"`.

**Result:** Every author-year citation returns `None` — silently fails. AE-6 would flag real papers as fabricated.

**Fix options:**

- **(A) Normalize in `loader.py`** — have `load_case()` apply the same alias map when reading table.csv, so `CaseData.table` dicts always use canonical keys (`"title"`, `"authors"`, `"year"`, etc.). One normalization point, all consumers benefit.
- **(B) Alias-aware `_get_col_ci()`** — make the lookup function know about aliases. Duplicates alias knowledge across two files.

**Recommendation:** Option A. Normalize once in the loader. Then `_get_col_ci()` works as-is because the keys are already canonical.

**Files:** `evals/shared/loader.py` (primary), `evals/shared/citation_parser.py` (may simplify)

---

### P1 Execution

```
Step 1: table_parser.py — replace _METADATA_COLUMNS with _METADATA_ALIASES
Step 2: loader.py — normalize CaseData.table dict keys via same alias map
Step 3: Verify parse_table() succeeds on samples/case_001/table.csv
Step 4: Verify match_citation_to_table() matches author-year citations
```

### P1 Unblocks

- **AE-5** can load paper records and match citations to papers
- **AE-6** correctly matches author-year citations (not just numeric)
- **AE-7** can load all papers as grounding sources

---

## P2: Token Optimization (nice-to-have, not blocking)

### P2-A: Garbage Focus Columns

**File:** `evals/shared/table_parser.py:170-172`

After P1, `parse_table()` will work — but `focus_columns` will contain 17 noise columns alongside the 3 useful ones. The LLM can ignore the noise (it won't produce wrong answers), but it wastes tokens, especially in AE-7 which sends all papers.

**Column audit:**

| Useful Focus Columns (3) | Garbage (17) |
|--------------------------|-------------|
| AI Methodology and Architecture | Paper Link, PDF Link, Publication Type, Publication Title |
| Performance Metrics | Open Access, Citations count, Google Scholar ID |
| Dataset and Validation Approach | PubMed ID, PMC ID, References, Grants |
| | arXiv ID, Updated Date, Primary Category |
| | Categories, Source, Relevance |

**Fix:** Add a denylist of known noise columns. A column becomes a focus column only if it's not in the alias map AND not in the denylist. New content columns from future agent runs auto-include; known noise is filtered.

```python
_SKIP_COLUMNS: frozenset[str] = frozenset({
    "paper link", "pdf link", "publication type", "publication title",
    "open access", "citations count", "google scholar id", "pubmed id",
    "pmc id", "references", "grants", "arxiv id", "updated date",
    "primary category", "categories", "source", "relevance",
})
```

**Files:** `evals/shared/table_parser.py`

---

### P2-B: AE-2 Plan Format Mismatch

**Severity:** Low — not a parser issue, just a prompt design note for when AE-2 is implemented.

The sprint doc assumes `todo.md` has section headings mappable to report sections. The actual `todo.md` is task-oriented ("Search scholarly literature...", "Extract performance metrics...") while the report is section-structured ("1. Introduction", "2. Background..."). The LLM must infer that task items imply topic coverage.

**Fix:** Handle in AE-2's prompt design (no parser changes):
- Send full plan text to LLM, not just extracted headings
- Instruct: "The plan may describe tasks rather than sections. Identify research topics implied by the plan, then check if the report covers each one."

**Files:** `evals/artifact/section_coverage.py` (when implemented)

---

### P2 Execution

P2 can be done anytime. No other work depends on it.

```
Step 1: table_parser.py — add _SKIP_COLUMNS denylist
Step 2: Verify focus_columns count drops from 20 to 3
Step 3: (AE-2 note — apply during Track A implementation)
```
