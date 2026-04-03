"""Unit tests for evals.shared.results — Finding, EvalResult, CaseResults."""

import json
import os
import tempfile

import pytest

from evals.shared.results import CaseResults, EvalResult, Finding


# ---------------------------------------------------------------------------
# Finding
# ---------------------------------------------------------------------------

class TestFinding:
    def test_basic_construction(self):
        f = Finding(severity="error", message="Citation missing", location="Section 2")
        assert f.severity == "error"
        assert f.message == "Citation missing"
        assert f.location == "Section 2"

    def test_optional_location(self):
        f = Finding(severity="info", message="Note")
        assert f.location is None

    def test_from_dict_roundtrip(self):
        original = Finding(severity="warning", message="Low score", location="Abstract")
        restored = Finding.from_dict(
            {"severity": "warning", "message": "Low score", "location": "Abstract"}
        )
        assert restored == original

    def test_from_dict_missing_location(self):
        f = Finding.from_dict({"severity": "info", "message": "OK"})
        assert f.location is None


# ---------------------------------------------------------------------------
# EvalResult
# ---------------------------------------------------------------------------

class TestEvalResult:
    def test_basic_construction(self):
        findings = [Finding(severity="error", message="Bad citation")]
        er = EvalResult(
            eval_name="citation_correctness",
            score=3.0,
            max_score=5.0,
            passed=False,
            findings=findings,
            reasoning="Some errors found.",
        )
        assert er.eval_name == "citation_correctness"
        assert er.passed is False
        assert len(er.findings) == 1

    def test_default_findings_and_reasoning(self):
        er = EvalResult(
            eval_name="test_eval", score=5.0, max_score=5.0, passed=True
        )
        assert er.findings == []
        assert er.reasoning == ""

    def test_from_dict_roundtrip(self):
        original = EvalResult(
            eval_name="grounding_check",
            score=4.0,
            max_score=5.0,
            passed=True,
            findings=[Finding(severity="warning", message="One weak link", location=None)],
            reasoning="Mostly grounded.",
        )
        from dataclasses import asdict
        restored = EvalResult.from_dict(asdict(original))
        assert restored == original


# ---------------------------------------------------------------------------
# CaseResults — serialization roundtrip
# ---------------------------------------------------------------------------

class TestCaseResults:
    def _sample_case_results(self) -> CaseResults:
        cr = CaseResults()
        cr.results.append(
            EvalResult(
                eval_name="citation_completeness",
                score=8.0,
                max_score=10.0,
                passed=True,
                findings=[Finding(severity="info", message="2 claims uncited")],
                reasoning="Mostly cited.",
            )
        )
        cr.results.append(
            EvalResult(
                eval_name="fabricated_references",
                score=10.0,
                max_score=10.0,
                passed=True,
                findings=[],
                reasoning="All references valid.",
            )
        )
        return cr

    def test_save_creates_json_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            case_path = os.path.join(tmpdir, "case_001")
            cr = self._sample_case_results()
            cr.save(case_path)

            out_file = os.path.join(case_path, "eval_results.json")
            assert os.path.isfile(out_file)

            with open(out_file) as fh:
                data = json.load(fh)
            assert isinstance(data, list)
            assert len(data) == 2

    def test_load_restores_results(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            case_path = os.path.join(tmpdir, "case_001")
            original = self._sample_case_results()
            original.save(case_path)

            loaded = CaseResults.load(case_path)
            assert len(loaded.results) == 2
            assert loaded.results[0].eval_name == "citation_completeness"
            assert loaded.results[0].score == 8.0
            assert loaded.results[0].findings[0].severity == "info"
            assert loaded.results[1].eval_name == "fabricated_references"

    def test_save_creates_directory_if_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            case_path = os.path.join(tmpdir, "new", "nested", "case")
            cr = CaseResults()
            cr.save(case_path)  # should not raise
            assert os.path.isfile(os.path.join(case_path, "eval_results.json"))

    def test_load_raises_on_missing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(FileNotFoundError):
                CaseResults.load(tmpdir)

    def test_roundtrip_empty_results(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            case_path = os.path.join(tmpdir, "case_empty")
            cr = CaseResults()
            cr.save(case_path)
            loaded = CaseResults.load(case_path)
            assert loaded.results == []

    def test_aggregation_helpers(self):
        cr = self._sample_case_results()
        assert cr.passed_count() == 2
        assert cr.total_score() == 18.0
        assert cr.total_max_score() == 20.0
