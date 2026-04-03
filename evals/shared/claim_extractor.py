"""Claim extraction from research report markdown using LLMJudge.

Identifies factual/empirical claims in a report, associates each claim with
its markdown section, detects inline citations, and flags numerical claims
(those containing digits combined with units or statistical terms).

Provides:
    Citation  — fallback dataclass (replaced at integration time by citation_parser)
    Claim     — a single extracted claim with context
    extract_claims() — top-level entry point
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from evals.shared.llm_judge import LLMJudge

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Citation — fallback definition
# ---------------------------------------------------------------------------
# The authoritative Citation lives in evals/shared/citation_parser.py (parsers
# sprint).  We try to import it; if that module isn't available yet we define a
# structurally-identical fallback so this module can be used independently.

try:
    from evals.shared.citation_parser import Citation  # type: ignore[import]
except ImportError:  # pragma: no cover — covered once parsers sprint lands
    @dataclass
    class Citation:  # type: ignore[no-redef]
        """Fallback Citation — matches parsers-sprint contract."""

        raw_text: str
        authors: list[str] | None = None
        year: int | None = None
        reference_id: str | None = None


# ---------------------------------------------------------------------------
# Claim
# ---------------------------------------------------------------------------

@dataclass
class Claim:
    """A single factual or empirical claim extracted from a research report.

    Attributes:
        text:         The verbatim sentence or phrase constituting the claim.
        section:      The nearest markdown heading above the claim, or
                      "unsectioned" when the report has no headings.
        citation:     Inline citation associated with the claim, or None.
        is_numerical: True when the claim contains digits alongside units or
                      statistical terminology (e.g. "95%", "3.2 kg", "p < 0.05").
    """

    text: str
    section: str
    citation: Citation | None
    is_numerical: bool


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def extract_claims(report: str, llm_judge: LLMJudge) -> list[Claim]:
    """Extract all factual/empirical claims from a markdown research report.

    Uses *llm_judge* to identify claims and associates each with its section,
    citation, and numerical status.

    Args:
        report:     Full markdown text of the research report.
        llm_judge:  Configured LLMJudge instance.

    Returns:
        List of Claim objects, one per identified factual statement.
    """
    # Pre-process: build a section-annotated version of the report so the LLM
    # receives context about which heading each paragraph belongs to.
    sections = _parse_sections(report)
    annotated_report = _build_annotated_report(sections)

    prompt = _build_extraction_prompt(annotated_report)
    response_schema = {
        "claims": (
            "array of objects, each with keys: "
            '"text" (string), '
            '"section" (string — heading title or "unsectioned"), '
            '"citation_raw" (string or null — the inline citation text verbatim), '
            '"is_numerical" (boolean)'
        )
    }

    logger.debug("Extracting claims from report (%d chars)", len(report))
    raw = llm_judge.judge(prompt, response_schema)

    claims_data = raw.get("claims", [])
    if not isinstance(claims_data, list):
        logger.warning("LLM returned non-list 'claims' field; defaulting to empty list")
        claims_data = []

    return [_build_claim(item) for item in claims_data if isinstance(item, dict)]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Regex patterns for inline citation detection.
# Matches: [Author, 2023], [Author et al., 2020], or numeric refs like [1] or [12].
_CITATION_PATTERN = re.compile(
    r"\[(?:[A-Za-z][^,\]]*,?\s*(?:et al\.,?)?\s*\d{4}|\d{1,3})\]"
)

# Numerical-claim detection: digit(s) + a unit or statistical term nearby.
_NUMERICAL_PATTERN = re.compile(
    r"\d"  # at least one digit present
    r"(?=.*(?:%|kg|g\b|mg|ml|mL|L\b|m\b|km|cm|mm|Hz|kHz|MHz|GHz"
    r"|p\s*[<>=]\s*0\.\d|CI\b|SD\b|SE\b|OR\b|HR\b|RR\b|fold"
    r"|\bsignificant|\bcoefficient|\bcorrelation|\bregression"
    r"|\bmean\b|\bmedian\b|\bproportion\b|\bprevalence\b|\bincidence\b"
    r"|\bparticipants\b|\bpatients\b|\bsubjects\b|\bsamples\b"
    r"|\baccuracy\b|\bsensitivity\b|\bspecificity\b|\bAUC\b"
    r"|\bF1\b|\bprecision\b|\brecall\b|\bperformance\b))",
    re.IGNORECASE,
)


def _parse_sections(report: str) -> list[tuple[str, str]]:
    """Split the report into (heading, body) pairs.

    Returns a list of ``(section_name, body_text)`` tuples in document order.
    When the report begins with content before the first heading that content
    is placed under the special section name "unsectioned".
    """
    heading_re = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
    matches = list(heading_re.finditer(report))

    if not matches:
        return [("unsectioned", report)]

    sections: list[tuple[str, str]] = []

    # Text before the first heading.
    preamble = report[: matches[0].start()].strip()
    if preamble:
        sections.append(("unsectioned", preamble))

    for i, match in enumerate(matches):
        heading = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(report)
        body = report[start:end].strip()
        sections.append((heading, body))

    return sections


def _build_annotated_report(sections: list[tuple[str, str]]) -> str:
    """Rebuild the report with explicit [SECTION: ...] tags for the LLM."""
    parts: list[str] = []
    for heading, body in sections:
        parts.append(f"[SECTION: {heading}]\n{body}")
    return "\n\n".join(parts)


def _build_extraction_prompt(annotated_report: str) -> str:
    return (
        "You are an expert scientific editor. "
        "Extract every factual or empirical claim from the following research report. "
        "A claim is a sentence or clause that asserts a specific fact, result, "
        "statistic, relationship, or finding that could in principle be verified "
        "against a source paper.\n\n"
        "For each claim include:\n"
        '  - "text": the verbatim sentence containing the claim\n'
        '  - "section": the section heading it appears under (from the [SECTION: ...] '
        'tags), or "unsectioned" if none\n'
        '  - "citation_raw": the inline citation string exactly as it appears '
        '(e.g. "[Smith, 2021]" or "[3]"), or null if no citation is present\n'
        '  - "is_numerical": true if the claim contains numbers alongside units, '
        "percentages, or statistical measures; false otherwise\n\n"
        "Report:\n\n"
        f"{annotated_report}"
    )


def _build_claim(item: dict) -> Claim:
    """Convert a single raw LLM claim dict into a typed Claim object."""
    text: str = item.get("text", "").strip()
    section: str = item.get("section", "unsectioned").strip() or "unsectioned"
    citation_raw: str | None = item.get("citation_raw") or None
    is_numerical: bool = bool(item.get("is_numerical", False))

    # Supplement/override the LLM's is_numerical flag with a local regex check
    # to catch cases the model may miss.
    if not is_numerical and _NUMERICAL_PATTERN.search(text):
        is_numerical = True

    # Build Citation from the raw citation text when present.
    citation: Citation | None = None
    if citation_raw:
        citation = _parse_inline_citation(citation_raw)

    return Claim(
        text=text,
        section=section,
        citation=citation,
        is_numerical=is_numerical,
    )


def _parse_inline_citation(raw: str) -> Citation:
    """Parse a raw inline citation string into a Citation object.

    Handles two common formats:
      - Author-year: "[Smith et al., 2021]" → authors=["Smith et al."], year=2021
      - Numeric ref: "[3]" → reference_id="3"
    """
    # Numeric reference: [1] to [999]
    numeric_match = re.match(r"^\[(\d{1,3})\]$", raw.strip())
    if numeric_match:
        return Citation(
            raw_text=raw,
            authors=None,
            year=None,
            reference_id=numeric_match.group(1),
        )

    # Author-year: "[Last, YYYY]" or "[Last et al., YYYY]"
    author_year_match = re.match(
        r"^\[([^,\]]+(?:,\s*et al\.?)?),?\s*(\d{4})\]$", raw.strip()
    )
    if author_year_match:
        author_str = author_year_match.group(1).strip()
        year = int(author_year_match.group(2))
        return Citation(
            raw_text=raw,
            authors=[author_str],
            year=year,
            reference_id=None,
        )

    # Unrecognised format — preserve raw text only.
    return Citation(raw_text=raw, authors=None, year=None, reference_id=None)
