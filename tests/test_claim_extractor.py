"""Unit tests for evals.shared.claim_extractor."""

import json
from unittest.mock import MagicMock

import pytest

from evals.shared.claim_extractor import (
    Claim,
    Citation,
    _parse_inline_citation,
    _parse_sections,
    extract_claims,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_judge(claims_payload: list[dict]) -> MagicMock:
    """Return a mock LLMJudge whose judge() returns the given claims list."""
    judge = MagicMock()
    judge.judge.return_value = {"claims": claims_payload}
    return judge


# ---------------------------------------------------------------------------
# _parse_sections
# ---------------------------------------------------------------------------

class TestParseSections:
    def test_no_headings_returns_unsectioned(self):
        report = "This is a plain report with no headings."
        sections = _parse_sections(report)
        assert len(sections) == 1
        assert sections[0][0] == "unsectioned"

    def test_single_heading(self):
        report = "# Introduction\nSome intro text."
        sections = _parse_sections(report)
        assert sections[0] == ("Introduction", "Some intro text.")

    def test_multiple_headings(self):
        report = (
            "# Methods\nWe used X.\n\n## Results\nWe found Y.\n\n# Conclusion\nDone."
        )
        sections = _parse_sections(report)
        names = [s[0] for s in sections]
        assert "Methods" in names
        assert "Results" in names
        assert "Conclusion" in names

    def test_preamble_before_first_heading(self):
        report = "Abstract text here.\n\n# Introduction\nBody."
        sections = _parse_sections(report)
        assert sections[0][0] == "unsectioned"
        assert sections[1][0] == "Introduction"

    def test_empty_report(self):
        sections = _parse_sections("")
        assert sections[0][0] == "unsectioned"


# ---------------------------------------------------------------------------
# _parse_inline_citation
# ---------------------------------------------------------------------------

class TestParseInlineCitation:
    def test_numeric_reference(self):
        c = _parse_inline_citation("[3]")
        assert c.reference_id == "3"
        assert c.authors is None
        assert c.year is None

    def test_author_year(self):
        c = _parse_inline_citation("[Smith, 2021]")
        assert c.authors == ["Smith"]
        assert c.year == 2021
        assert c.reference_id is None

    def test_author_et_al_year(self):
        c = _parse_inline_citation("[Jones et al., 2019]")
        assert c.authors is not None
        assert "Jones" in c.authors[0]
        assert c.year == 2019

    def test_unrecognised_format_preserved(self):
        raw = "[weird format XYZ]"
        c = _parse_inline_citation(raw)
        assert c.raw_text == raw
        assert c.authors is None


# ---------------------------------------------------------------------------
# extract_claims
# ---------------------------------------------------------------------------

class TestExtractClaims:
    def test_basic_claim_creation(self):
        payload = [
            {
                "text": "Treatment reduced mortality by 20%.",
                "section": "Results",
                "citation_raw": "[Smith, 2021]",
                "is_numerical": True,
            }
        ]
        judge = _make_mock_judge(payload)
        claims = extract_claims("# Results\nTreatment reduced mortality by 20% [Smith, 2021].", judge)

        assert len(claims) == 1
        c = claims[0]
        assert c.text == "Treatment reduced mortality by 20%."
        assert c.section == "Results"
        assert c.is_numerical is True
        assert c.citation is not None
        assert c.citation.year == 2021

    def test_claim_without_citation(self):
        payload = [
            {
                "text": "The drug is effective.",
                "section": "Discussion",
                "citation_raw": None,
                "is_numerical": False,
            }
        ]
        judge = _make_mock_judge(payload)
        claims = extract_claims("# Discussion\nThe drug is effective.", judge)

        assert claims[0].citation is None
        assert claims[0].is_numerical is False

    def test_no_sections_fallback(self):
        payload = [
            {
                "text": "Results were positive.",
                "section": "unsectioned",
                "citation_raw": None,
                "is_numerical": False,
            }
        ]
        judge = _make_mock_judge(payload)
        claims = extract_claims("Results were positive.", judge)

        assert claims[0].section == "unsectioned"

    def test_empty_claims_list(self):
        judge = _make_mock_judge([])
        claims = extract_claims("No claims here.", judge)
        assert claims == []

    def test_llm_judge_called_once(self):
        judge = _make_mock_judge([])
        extract_claims("# Intro\nSome text.", judge)
        assert judge.judge.call_count == 1

    def test_numerical_flag_supplemented_by_regex(self):
        # LLM says not numerical, but text contains "3.2 kg" — regex should catch it.
        payload = [
            {
                "text": "Participants weighed 3.2 kg less after treatment.",
                "section": "Results",
                "citation_raw": None,
                "is_numerical": False,  # LLM missed it
            }
        ]
        judge = _make_mock_judge(payload)
        claims = extract_claims("# Results\nParticipants weighed 3.2 kg less.", judge)
        assert claims[0].is_numerical is True

    def test_non_list_claims_field_handled_gracefully(self):
        judge = MagicMock()
        judge.judge.return_value = {"claims": "oops not a list"}
        claims = extract_claims("Some text.", judge)
        assert claims == []

    def test_prompt_contains_report_text(self):
        judge = _make_mock_judge([])
        report = "# Methods\nWe recruited 50 participants."
        extract_claims(report, judge)

        call_kwargs = judge.judge.call_args
        prompt_arg = call_kwargs[0][0]  # first positional arg
        assert "50 participants" in prompt_arg

    def test_numeric_reference_citation(self):
        payload = [
            {
                "text": "Results confirmed the hypothesis.",
                "section": "Results",
                "citation_raw": "[12]",
                "is_numerical": False,
            }
        ]
        judge = _make_mock_judge(payload)
        claims = extract_claims("# Results\nResults confirmed [12].", judge)
        assert claims[0].citation.reference_id == "12"
