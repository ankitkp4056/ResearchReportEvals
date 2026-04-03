"""
evals/shared/loader.py
----------------------
Loads a single agent-run case directory into a structured CaseData object.

Each case directory contains four artifacts produced by the research agent:
  - query.txt   : the raw user query
  - todo.md     : the planning doc (Step 1 artifact)
  - table.csv   : the final extraction table (Step 5 artifact)
  - report.md   : the generated report (Step 6 artifact)

Usage:
    from evals.shared.loader import load_case
    case = load_case("samples/case_001")
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# Data contract
# ---------------------------------------------------------------------------

@dataclass
class CaseData:
    """All artifacts for one agent run, loaded into memory."""
    query: str               # raw user query string
    plan: str                # planning doc (todo.md) content
    table: list[dict]        # CSV rows as dicts, keyed by original header names
    report: str              # report markdown content
    case_path: Path          # absolute path to the case directory


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_case(case_path: str) -> CaseData:
    """Load all four artifacts from a case directory.

    Args:
        case_path: Path to the case directory (e.g. "samples/case_001").
                   Accepts a string; converted internally to pathlib.Path.

    Returns:
        CaseData with all four artifacts populated.

    Raises:
        FileNotFoundError: If the case directory or any required file is missing.
        ValueError:        If the CSV is empty or has no header row.
    """
    root = Path(case_path).resolve()

    if not root.exists():
        raise FileNotFoundError(f"Case directory not found: {root}")
    if not root.is_dir():
        raise FileNotFoundError(f"Case path is not a directory: {root}")

    # -- Text files -----------------------------------------------------------
    query  = _read_text(root / "query.txt")
    plan   = _read_text(root / "todo.md")
    report = _read_text(root / "report.md")

    # -- CSV ------------------------------------------------------------------
    csv_path = root / "table.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Required file missing: {csv_path}")

    # Open with newline="" as required by Python's csv module docs.
    with csv_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header row: {csv_path}")
        rows = list(reader)

    if not rows:
        raise ValueError(f"CSV is empty (header only): {csv_path}")

    return CaseData(
        query=query,
        plan=plan,
        table=rows,
        report=report,
        case_path=root,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _read_text(path: Path) -> str:
    """Read a UTF-8 text file, stripping trailing whitespace from each line."""
    if not path.exists():
        raise FileNotFoundError(f"Required file missing: {path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    # Strip trailing whitespace per line, then rejoin preserving structure.
    return "\n".join(line.rstrip() for line in lines)
