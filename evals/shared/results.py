"""Result schema dataclasses for the eval suite.

Provides three types:

    Finding    — a single annotated observation (error / warning / info)
    EvalResult — the outcome of one eval on one case
    CaseResults — aggregated results for a full case, with JSON save/load
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict, field
from typing import Any


# ---------------------------------------------------------------------------
# Finding
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    """A single annotated observation produced during an eval.

    Attributes:
        severity: One of "error", "warning", or "info".
        message:  Human-readable description of the finding.
        location: Optional reference to the specific location in the artifact
                  (e.g. section name, line number, citation id).
    """

    severity: str  # "error" | "warning" | "info"
    message: str
    location: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Finding":
        return cls(
            severity=d["severity"],
            message=d["message"],
            location=d.get("location"),
        )


# ---------------------------------------------------------------------------
# EvalResult
# ---------------------------------------------------------------------------

@dataclass
class EvalResult:
    """The outcome of running a single eval against a single case.

    Attributes:
        eval_name:  Identifier for the eval, e.g. "citation_completeness".
        score:      Numeric score achieved.
        max_score:  Maximum achievable score (used to compute percentage).
        passed:     Convenience boolean; typically True when score >= threshold.
        findings:   List of individual Finding observations.
        reasoning:  Free-text explanation from the LLM or the eval script.
    """

    eval_name: str
    score: float
    max_score: float
    passed: bool
    findings: list[Finding] = field(default_factory=list)
    reasoning: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "EvalResult":
        findings = [Finding.from_dict(f) for f in d.get("findings", [])]
        return cls(
            eval_name=d["eval_name"],
            score=d["score"],
            max_score=d["max_score"],
            passed=d["passed"],
            findings=findings,
            reasoning=d.get("reasoning", ""),
        )


# ---------------------------------------------------------------------------
# CaseResults
# ---------------------------------------------------------------------------

class CaseResults:
    """Aggregated eval results for a single agent-run case.

    Stores a list of EvalResult objects and can round-trip to/from a JSON
    file named ``eval_results.json`` inside the case directory.

    Usage::

        results = CaseResults()
        results.results.append(some_eval_result)
        results.save("samples/case_001")

        loaded = CaseResults.load("samples/case_001")
    """

    FILENAME = "eval_results.json"

    def __init__(self, results: list[EvalResult] | None = None) -> None:
        self.results: list[EvalResult] = results if results is not None else []

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, case_path: str) -> None:
        """Serialize results to ``{case_path}/eval_results.json``.

        Creates the directory if it does not already exist.
        """
        os.makedirs(case_path, exist_ok=True)
        out_path = os.path.join(case_path, self.FILENAME)
        payload = [asdict(r) for r in self.results]
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)

    @classmethod
    def load(cls, case_path: str) -> "CaseResults":
        """Deserialize results from ``{case_path}/eval_results.json``.

        Raises:
            FileNotFoundError: If the JSON file does not exist.
        """
        in_path = os.path.join(case_path, cls.FILENAME)
        with open(in_path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
        results = [EvalResult.from_dict(item) for item in payload]
        return cls(results=results)

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return f"CaseResults(results={self.results!r})"

    def passed_count(self) -> int:
        """Number of evals that passed."""
        return sum(1 for r in self.results if r.passed)

    def total_score(self) -> float:
        """Sum of all individual scores."""
        return sum(r.score for r in self.results)

    def total_max_score(self) -> float:
        """Sum of all max_scores."""
        return sum(r.max_score for r in self.results)
