"""
evals/shared/citation_parser.py
---------------------------------
Extracts inline citations from a research report and attempts to match them
back to rows in the agent's extraction table.

Three citation formats are supported:
  1. Parenthetical author-year:  (Johnson & Williams, 2019)
                                 (Patel et al., 2021)
                                 (Chen, 2023)
  2. Bracket author-year:        [Johnson & Williams, 2019]
                                 [Patel et al., 2021]
  3. Numeric reference:          [1]  [7]  [12]

For author-year formats the author surname(s) and year are parsed into the
Citation dataclass.  For numeric citations only reference_id is set.

Usage (standalone):
    python -m evals.shared.citation_parser samples/case_001/report.md
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Year: four-digit number in the range 1900–2099
_YEAR_PART = r"(?P<year>(?:19|20)\d{2})"

# Matches an author cluster: one or more words that may include "&", "et al.",
# dots, and spaces — up to but not including a comma+year or closing delimiter.
# Named group "authors" is captured.
#   Examples:
#     "Johnson & Williams"
#     "Patel et al."
#     "Chen & Nakamura"
#     "Lee et al"           (no trailing period)
_AUTHOR_PART = r"(?P<authors>[A-Za-z][^,\[\]()\d]{2,}?)(?:\.|(?=\s*,\s*\d{4}))"

# Author-year in parentheses: (Author..., YYYY)
#   e.g.  (Johnson & Williams, 2019)
_PAREN_AUTHOR_YEAR_RE = re.compile(
    r"\(" + _AUTHOR_PART + r"\s*,\s*" + _YEAR_PART + r"\)"
)

# Author-year in brackets: [Author..., YYYY]
#   e.g.  [Johnson & Williams, 2019]
_BRACKET_AUTHOR_YEAR_RE = re.compile(
    r"\[" + _AUTHOR_PART + r"\s*,\s*" + _YEAR_PART + r"\]"
)

# Narrative author-year: Author (YYYY)  — author appears outside the paren.
# Captures the author tokens immediately before the opening paren.
#   e.g.  Johnson & Williams (2019)
#          Patel et al. (2021)
#          Lee et al. (2022)
# The author segment is anchored to word boundaries and must end right before
# the opening paren (allowing optional space).
_NARRATIVE_AUTHOR_YEAR_RE = re.compile(
    r"(?P<authors>[A-Z][A-Za-z]+(?:\s+(?:et\s+al\.?|&\s+[A-Z][A-Za-z]+))*)"
    r"\s+\((?P<year>(?:19|20)\d{2})\)"
)

# Numeric reference: [N] — pure integer in brackets.
# Must not contain letters (avoids colliding with bracket author-year format).
_NUMERIC_RE = re.compile(r"\[(\d+)\]")

# Split author strings on "&", "and", and "," (to isolate individual surnames).
_AUTHOR_SPLIT_RE = re.compile(r"[,&]|\band\b", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Data contract
# ---------------------------------------------------------------------------

@dataclass
class Citation:
    """A single citation extracted from a report."""
    raw_text: str                         # the full match as it appeared in text
    authors: list[str] | None             # last-name tokens; None for numeric refs
    year: int | None                      # publication year; None for numeric refs
    reference_id: str | None = None       # numeric ref id (e.g. "7"); None for author-year


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def extract_citations(report: str) -> list[Citation]:
    """Extract all inline citations from a report string.

    Parses three citation formats (parenthetical author-year, bracket
    author-year, numeric).  Results are deduplicated by raw_text and returned
    in order of first appearance.

    Args:
        report: Full text of the research report.

    Returns:
        List of Citation objects, ordered by first appearance, deduplicated.
    """
    seen: dict[str, Citation] = {}  # raw_text -> Citation, preserves insertion order

    for citation in _iter_citations(report):
        if citation.raw_text not in seen:
            seen[citation.raw_text] = citation

    return list(seen.values())


def match_citation_to_table(
    citation: Citation,
    table: list[dict],
) -> dict | None:
    """Attempt to match a Citation to a row in the raw CSV table.

    Matching strategy:
    - Author-year citations: find first table row whose "Authors" column
      contains any of the citation's author surnames (case-insensitive
      substring) AND whose "Year" column equals the citation year.
    - Numeric citations: return None — numeric refs cannot be resolved
      without an explicit reference list.

    Table rows are raw dicts from csv.DictReader.  Column name lookup is
    case-insensitive.

    Args:
        citation: Citation object to resolve.
        table:    Raw list[dict] from the loader (csv.DictReader rows).

    Returns:
        The first matching table row dict, or None.
    """
    # Numeric citations cannot be matched structurally.
    if citation.reference_id is not None and citation.authors is None:
        return None

    if not citation.authors or citation.year is None:
        return None

    for row in table:
        row_authors = _get_col_ci(row, "authors") or ""
        row_year    = _get_col_ci(row, "year")    or ""

        # Year must match exactly.
        try:
            if int(row_year.strip()) != citation.year:
                continue
        except (ValueError, AttributeError):
            continue

        # At least one cited surname must appear in the row's Authors cell.
        row_authors_lower = row_authors.lower()
        if any(name.lower() in row_authors_lower for name in citation.authors):
            return row

    return None


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _iter_citations(text: str) -> Iterator[Citation]:
    """Yield Citation objects for every citation found in text, in order."""
    # Collect all matches across all patterns together with their start
    # positions so we can return them in order of appearance.
    matches: list[tuple[int, Citation]] = []

    for m in _PAREN_AUTHOR_YEAR_RE.finditer(text):
        matches.append((m.start(), _build_author_year_citation(m)))

    for m in _BRACKET_AUTHOR_YEAR_RE.finditer(text):
        matches.append((m.start(), _build_author_year_citation(m)))

    for m in _NARRATIVE_AUTHOR_YEAR_RE.finditer(text):
        matches.append((m.start(), _build_author_year_citation(m)))

    for m in _NUMERIC_RE.finditer(text):
        matches.append((
            m.start(),
            Citation(
                raw_text=m.group(0),
                authors=None,
                year=None,
                reference_id=m.group(1),
            ),
        ))

    # Sort by position in text.
    matches.sort(key=lambda t: t[0])
    for _, citation in matches:
        yield citation


def _build_author_year_citation(match: re.Match) -> Citation:
    """Construct a Citation from a regex match with 'authors' and 'year' groups."""
    raw_authors_str = match.group("authors").strip()
    year_str        = match.group("year")

    # Remove "et al." (with or without trailing period) from the author string
    # before splitting, then extract individual clean surnames.
    cleaned = re.sub(r"\bet\s+al\.?", "", raw_authors_str, flags=re.IGNORECASE)
    parts   = _AUTHOR_SPLIT_RE.split(cleaned)
    # Strip whitespace and any trailing/leading punctuation (dots, commas).
    surnames = [p.strip().strip(".,") for p in parts if p.strip().strip(".,")]

    return Citation(
        raw_text=match.group(0),
        authors=surnames if surnames else None,
        year=int(year_str),
        reference_id=None,
    )


def _get_col_ci(row: dict, key_lower: str) -> str | None:
    """Case-insensitive column lookup on a csv.DictReader row dict."""
    for k, v in row.items():
        if k.strip().lower() == key_lower:
            return v
    return None


# ---------------------------------------------------------------------------
# Standalone entry point for quick inspection
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m evals.shared.citation_parser <path/to/report.md>")
        sys.exit(1)

    text = Path(sys.argv[1]).read_text(encoding="utf-8")
    citations = extract_citations(text)
    print(f"Found {len(citations)} unique citation(s):\n")
    for c in citations:
        if c.reference_id is not None:
            print(f"  [numeric] id={c.reference_id!r}  raw={c.raw_text!r}")
        else:
            print(f"  [author-year] authors={c.authors}  year={c.year}  raw={c.raw_text!r}")
