"""
evals/shared/table_parser.py
-----------------------------
Parses the agent's extraction table (table.csv) into structured PaperRecord
objects, and provides fuzzy title-based lookup.

Column-name resolution uses case-insensitive matching against a fixed set of
known metadata columns (title, authors, year, doi, abstract).  All remaining
columns are stored in `focus_columns` with their original header names as keys.

Usage (standalone):
    python -m evals.shared.table_parser samples/case_001/table.csv
"""

from __future__ import annotations

import csv
import difflib
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Lowercase names of the fixed metadata columns.  All other columns become
# focus_columns keys (preserving original capitalisation).
_METADATA_COLUMNS: frozenset[str] = frozenset({"title", "authors", "year", "doi", "abstract"})

# Default fuzzy-match threshold for get_paper_by_title.
_FUZZY_THRESHOLD: float = 0.6


# ---------------------------------------------------------------------------
# Data contract
# ---------------------------------------------------------------------------

@dataclass
class PaperRecord:
    """Structured representation of one row from table.csv."""
    title: str
    authors: str
    year: int
    doi: str | None
    abstract: str | None
    focus_columns: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def parse_table(csv_path: str) -> list[PaperRecord]:
    """Parse table.csv into a list of PaperRecord objects.

    Column names are matched case-insensitively against the metadata set.
    Non-metadata columns are stored verbatim in focus_columns.

    Args:
        csv_path: Path to the CSV file.

    Returns:
        List of PaperRecord, one per data row.

    Raises:
        FileNotFoundError: If csv_path does not exist.
        ValueError:        If required columns (title, authors, year) are absent,
                           or if a year value cannot be parsed as an integer.
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Table CSV not found: {path}")

    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header row: {path}")

        # Build a mapping from lowercase header -> original header for all cols.
        header_map: dict[str, str] = {col.strip().lower(): col for col in reader.fieldnames}
        _validate_required_columns(header_map, path)

        records: list[PaperRecord] = []
        for row_num, row in enumerate(reader, start=2):  # start=2: row 1 is header
            records.append(_row_to_record(row, header_map, row_num))

    return records


def get_paper_by_title(
    table: list[PaperRecord],
    query: str,
    threshold: float = _FUZZY_THRESHOLD,
) -> PaperRecord | None:
    """Fuzzy-match a query string against paper titles.

    Comparison is case-insensitive.  Returns the best-matching PaperRecord
    whose similarity ratio is >= threshold, or None if no match qualifies.

    Args:
        table:     List of PaperRecord objects to search.
        query:     Title string to look up.
        threshold: Minimum SequenceMatcher ratio (0–1).  Default: 0.6.

    Returns:
        Best-matching PaperRecord, or None.
    """
    query_lower = query.lower().strip()
    best_record: PaperRecord | None = None
    best_ratio: float = 0.0

    for record in table:
        ratio = difflib.SequenceMatcher(
            None, query_lower, record.title.lower()
        ).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_record = record

    if best_ratio >= threshold:
        return best_record
    return None


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _validate_required_columns(header_map: dict[str, str], path: Path) -> None:
    """Raise ValueError if any mandatory metadata column is absent."""
    required = {"title", "authors", "year"}
    missing = required - header_map.keys()
    if missing:
        raise ValueError(
            f"CSV {path} is missing required columns: {', '.join(sorted(missing))}"
        )


def _row_to_record(
    row: dict[str, str | None],
    header_map: dict[str, str],
    row_num: int,
) -> PaperRecord:
    """Convert a single DictReader row into a PaperRecord."""
    def get(col_lower: str) -> str:
        """Return the cell value for a metadata column, stripped."""
        original = header_map[col_lower]
        return (row.get(original) or "").strip()

    # -- Mandatory fields -----------------------------------------------------
    title   = get("title")
    authors = get("authors")
    year_str = get("year")

    try:
        year = int(year_str)
    except ValueError:
        raise ValueError(
            f"Row {row_num}: cannot parse year as integer: {year_str!r}"
        )

    # -- Optional metadata fields ---------------------------------------------
    doi_val      = get("doi")      if "doi"      in header_map else ""
    abstract_val = get("abstract") if "abstract" in header_map else ""

    doi      = doi_val      or None
    abstract = abstract_val or None

    # -- Focus columns (everything not in the metadata set) -------------------
    focus_columns: dict[str, str] = {}
    for col_lower, original_col in header_map.items():
        if col_lower not in _METADATA_COLUMNS:
            focus_columns[original_col] = (row.get(original_col) or "").strip()

    return PaperRecord(
        title=title,
        authors=authors,
        year=year,
        doi=doi,
        abstract=abstract,
        focus_columns=focus_columns,
    )


# ---------------------------------------------------------------------------
# Standalone entry point for quick inspection
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m evals.shared.table_parser <path/to/table.csv>")
        sys.exit(1)

    records = parse_table(sys.argv[1])
    for r in records:
        print(f"  [{r.year}] {r.authors} — {r.title}")
        print(f"         DOI: {r.doi}")
        print(f"         Focus: {r.focus_columns}")
