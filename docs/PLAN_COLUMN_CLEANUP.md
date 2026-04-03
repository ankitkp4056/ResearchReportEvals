# Plan: Column & Data Cleanup for Track A + Track B Evals

**Status:** Planning (no code changes yet)

---

## Problem Summary

The actual `samples/case_001/table.csv` (2,521 rows, 25 columns) has different column names and far more columns than what the parsers were designed for. This causes:

1. **`table_parser.py` fails immediately** on real data — column name mismatch
2. **`citation_parser.py` can't match author-year citations** to table rows — same root cause
3. **20 garbage columns** would flow into LLM prompts as `focus_columns` — wasting tokens, adding noise
4. **Track A has a minor semantic mismatch** in AE-2 — plan is task-oriented, not section-oriented

### Impact by Eval

| Eval | Status | Blocker |
|------|--------|---------|
| AE-1 (Planning Faithfulness) | OK | None — uses query + plan only |
| AE-2 (Section Coverage) | Fragile | Plan format is task-oriented, not section headings |
| AE-3 (Analysis Depth) | OK | None — uses query + report only |
| AE-4 (Citation Completeness) | OK | No table.csv dependency |
| AE-5 (Citation Correctness) | **BROKEN** | table_parser fails; can't load paper records |
| AE-6 (Fabricated References) | Partial | Numeric citations work; author-year matching broken |
| AE-7 (Grounding Check) | **BROKEN** | table_parser fails; focus_columns bloated with noise |

---

## Issue 1: Column Name Mismatch in `table_parser.py`

**File:** `evals/shared/table_parser.py:28`

**Root cause:** `_METADATA_COLUMNS` expects exact lowercase names that don't exist in the CSV.

```
Expected (metadata set)     Actual CSV Header         Match?
───────────────────────     ─────────────────         ──────
title                       Paper Title               NO
authors                     Author Names              NO
year                        Publication Year          NO
doi                         DOI                       YES
abstract                    Abstract                  YES
```

**Result:** `parse_table()` raises `ValueError: CSV is missing required columns: authors, title, year` before any eval can run.

### Fix

Expand `_METADATA_COLUMNS` into an alias map so each logical field can match multiple column names:

```python
_METADATA_ALIASES: dict[str, list[str]] = {
    "title":    ["title", "paper title"],
    "authors":  ["authors", "author names"],
    "year":     ["year", "publication year"],
    "doi":      ["doi"],
    "abstract": ["abstract"],
}
```

Resolution logic: for each metadata field, scan the CSV headers (lowercased) against the alias list. First match wins. Everything that doesn't match any alias becomes a focus column.

**Files changed:** `evals/shared/table_parser.py`

---

## Issue 2: Column Lookup Bug in `citation_parser.py`

**File:** `evals/shared/citation_parser.py` — `_get_col_ci()` helper and `match_citation_to_table()`

**Root cause:** `match_citation_to_table()` looks up `"authors"` and `"year"` in raw `dict` rows from `csv.DictReader`. The case-insensitive lookup compares the full lowercased key, but the actual keys are `"Author Names"` and `"Publication Year"` — these will never match `"authors"` or `"year"`.

```python
# Current: exact lowercase match
if k.strip().lower() == key_lower:  # "author names" != "authors" → MISS
```

### Fix

Apply the same alias map from Issue 1. Either:

- **(A) Normalize at the loader level:** Have `load_case()` normalize CSV column names when reading `table.csv` into `list[dict]`, so downstream code always sees `"title"`, `"authors"`, `"year"`, etc. This is the cleanest fix — one normalization point, all consumers benefit.
- **(B) Alias-aware lookup in citation_parser:** Make `_get_col_ci()` aware of multiple possible column names. Works but duplicates alias knowledge.

**Recommendation:** Option A — normalize in `loader.py`. The `CaseData.table` field should contain dicts with canonical lowercase keys. This fixes both `citation_parser` and any future consumer.

**Files changed:** `evals/shared/loader.py` (primary), `evals/shared/citation_parser.py` (simplify lookup)

---

## Issue 3: Garbage Focus Columns

**File:** `evals/shared/table_parser.py:170-172`

**Root cause:** `table_parser` treats ALL non-metadata columns as `focus_columns`. With 25 CSV columns and only 5 metadata matches, that's 20 focus columns — most of which are identifiers and metadata noise.

### Full Column Audit

| Column | Category | Useful for LLM Judging? |
|--------|----------|------------------------|
| Paper Title | Metadata (alias → `title`) | Yes — context |
| Author Names | Metadata (alias → `authors`) | Yes — matching |
| Publication Year | Metadata (alias → `year`) | Yes — matching |
| DOI | Metadata | No — identifier only |
| Abstract | Metadata | **Yes — primary content** |
| AI Methodology and Architecture | Focus | **Yes — extracted content** |
| Performance Metrics | Focus | **Yes — extracted content** |
| Dataset and Validation Approach | Focus | **Yes — extracted content** |
| Paper Link | Noise | No |
| PDF Link | Noise | No |
| Publication Type | Noise | No |
| Publication Title | Noise | No (journal name) |
| Open Access | Noise | No |
| Citations count | Noise | No |
| Google Scholar ID | Noise | No |
| PubMed ID | Noise | No |
| PMC ID | Noise | No |
| References | Noise | No |
| Grants | Noise | No |
| arXiv ID | Noise | No |
| Updated Date | Noise | No |
| Primary Category | Noise | No |
| Categories | Noise | No |
| Source | Noise | No |
| Relevance | Noise | No |

**Content-bearing columns (3):** AI Methodology and Architecture, Performance Metrics, Dataset and Validation Approach

**Garbage columns (17):** Everything else that isn't metadata or content

### Fix

Add an exclusion set to `table_parser.py` — columns that are known identifiers/metadata noise and should never be focus columns:

```python
_SKIP_COLUMNS: frozenset[str] = frozenset({
    "paper link", "pdf link", "publication type", "publication title",
    "open access", "citations count", "google scholar id", "pubmed id",
    "pmc id", "references", "grants", "arxiv id", "updated date",
    "primary category", "categories", "source", "relevance",
})
```

A column becomes a focus column only if its lowercased name is NOT in `_METADATA_ALIASES` and NOT in `_SKIP_COLUMNS`. This keeps the parser general — new content columns from future agent runs will automatically become focus columns, but known noise is filtered.

**Alternative considered:** Allowlist instead of denylist (only include columns explicitly named as focus). Rejected because focus columns vary per query topic — we can't predict them. A denylist of known noise is more maintainable.

**Files changed:** `evals/shared/table_parser.py`

---

## Issue 4: AE-2 Plan Format Mismatch (Track A)

**Severity:** Medium — not a blocker but affects eval quality.

**Root cause:** The sprint doc assumes `todo.md` contains section headings / topic areas that can be mapped to report sections. But the actual `todo.md` is task-oriented:

```markdown
## Literature Search
  - [x] Search scholarly literature on AI cancer detection
  - [x] Focus on imaging, genomics, and multimodal approaches
## Extract Insights
  - [x] Extract performance metrics from search results
## Report Writing
  - [x] Write a structured report with comparisons
```

While the report is section-structured:
```markdown
## 1. Introduction
## 2. Background and Theoretical Foundations
## 3. Methods and Approaches in the Literature
## 4. Key Findings and Comparative Analysis
## 5. Discussion
...
```

The LLM must infer that "Focus on imaging, genomics, multimodal" maps to sections 3.2-3.4 and 4.1-4.3. This is indirect but workable.

### Fix

No parser change needed. Handle in AE-2's prompt design:

1. Don't just extract headings from todo.md — extract **topic areas and research focus items** from bullet points too
2. Instruct the LLM explicitly: "The plan may describe tasks rather than sections. Identify the research topics and focus areas implied by the plan, then check if the report covers each one."
3. Consider sending the full plan text to the LLM rather than pre-parsed headings, so the LLM can interpret task items as implicit topic requirements

**Files changed:** `evals/artifact/section_coverage.py` (when implemented — prompt design only)

---

## Execution Order

Changes are independent and can be done in any order, but this sequence minimizes rework:

```
Step 1: Fix table_parser.py
        - Add _METADATA_ALIASES for column name resolution
        - Add _SKIP_COLUMNS to filter garbage from focus_columns
        - Verify parse_table() succeeds on actual table.csv

Step 2: Fix loader.py
        - Normalize CaseData.table dict keys to canonical lowercase names
        - This automatically fixes citation_parser column lookups

Step 3: Simplify citation_parser.py
        - Remove _get_col_ci() workarounds since loader now normalizes keys
        - Verify match_citation_to_table() works with normalized dicts

Step 4: Verify end-to-end
        - Run parse_table() on samples/case_001/table.csv
        - Confirm 3 focus columns, not 20
        - Run extract_citations() + match_citation_to_table() on report
        - Confirm citation matching works for both numeric and author-year formats

Step 5: Note for AE-2 implementation
        - When building section_coverage.py, use full plan text in prompt
        - Design prompt to handle task-oriented plans (not just section lists)
```

---

## What This Unblocks

After these fixes:
- **AE-5** can load paper records, match citations to papers, send (claim + title + abstract + 3 focus columns) to LLM
- **AE-6** can match author-year citations to table rows (currently only numeric works)
- **AE-7** can load all papers as grounding sources with clean content fields
- **AE-2** has guidance for prompt design that handles task-oriented plans

No changes needed for AE-1, AE-3, or AE-4 — they don't touch table.csv.
