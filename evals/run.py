"""Eval runner and CLI entry point.

Discovers registered evals, checks artifact availability, runs applicable
evals against a case, and writes aggregated results to ``eval_results.json``.

Usage:
    python -m evals.run samples/case_001/              # run all evals
    python -m evals.run samples/case_001/ --only ae-6   # run specific evals
"""

from __future__ import annotations

import argparse
import logging
import sys
import traceback
from typing import Callable

from evals.shared.loader import CaseData, load_case
from evals.shared.results import CaseResults, EvalResult

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

# Each entry maps an eval name to its callable and required artifact keys.
# Required artifacts are attribute names on CaseData that must be non-empty.
EVAL_REGISTRY: dict[str, dict] = {}


def register_eval(
    name: str,
    fn: Callable[[CaseData], EvalResult],
    required_artifacts: list[str],
) -> None:
    """Register an eval function in the global registry."""
    EVAL_REGISTRY[name] = {
        "fn": fn,
        "required_artifacts": required_artifacts,
    }


# ---------------------------------------------------------------------------
# Register built-in evals
# ---------------------------------------------------------------------------

from evals.artifact.fabricated_references import (  # noqa: E402
    EVAL_NAME as _ae6_name,
    REQUIRED_ARTIFACTS as _ae6_artifacts,
    evaluate_fabricated_references as _ae6_fn,
)

register_eval(_ae6_name, _ae6_fn, _ae6_artifacts)

from evals.artifact.planning_faithfulness import (  # noqa: E402
    EVAL_NAME as _ae1_name,
    REQUIRED_ARTIFACTS as _ae1_artifacts,
    evaluate_planning_faithfulness as _ae1_fn,
)

register_eval(_ae1_name, _ae1_fn, _ae1_artifacts)

from evals.artifact.section_coverage import (  # noqa: E402
    EVAL_NAME as _ae2_name,
    REQUIRED_ARTIFACTS as _ae2_artifacts,
    evaluate_section_coverage as _ae2_fn,
)

register_eval(_ae2_name, _ae2_fn, _ae2_artifacts)

from evals.artifact.analysis_depth import (  # noqa: E402
    EVAL_NAME as _ae3_name,
    REQUIRED_ARTIFACTS as _ae3_artifacts,
    evaluate_analysis_depth as _ae3_fn,
)

register_eval(_ae3_name, _ae3_fn, _ae3_artifacts)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

_ARTIFACT_ATTR_MAP: dict[str, str] = {
    "report": "report",
    "table": "table",
    "plan": "plan",
    "query": "query",
}


def _has_artifacts(case: CaseData, required: list[str]) -> bool:
    """Return True if *case* has all required artifacts populated."""
    for key in required:
        attr = _ARTIFACT_ATTR_MAP.get(key, key)
        value = getattr(case, attr, None)
        if not value:
            return False
    return True


def run_evals(
    case_path: str,
    only: list[str] | None = None,
) -> CaseResults:
    """Load a case and run all (or selected) evals against it.

    Args:
        case_path: Path to the case directory.
        only:      Optional list of eval names to run. If None, all registered
                   evals are run.

    Returns:
        CaseResults containing an EvalResult per executed eval.
    """
    case = load_case(case_path)
    results = CaseResults()

    eval_names = list(only) if only else list(EVAL_REGISTRY.keys())

    for name in eval_names:
        entry = EVAL_REGISTRY.get(name)
        if entry is None:
            logger.warning("Unknown eval %r — skipping", name)
            continue

        if not _has_artifacts(case, entry["required_artifacts"]):
            logger.warning(
                "Eval %r requires artifacts %s but case is missing some — skipping",
                name,
                entry["required_artifacts"],
            )
            continue

        try:
            result = entry["fn"](case)
            results.results.append(result)
        except Exception:
            logger.error("Eval %r failed:\n%s", name, traceback.format_exc())
            results.results.append(EvalResult(
                eval_name=name,
                score=0.0,
                max_score=1.0,
                passed=False,
                findings=[],
                reasoning=f"Eval crashed: {traceback.format_exc()}",
            ))

    return results


# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------

def _print_summary(results: CaseResults) -> None:
    """Print a summary table to stdout."""
    header = f"{'Eval':<30} {'Score':>6} {'Max':>6} {'Pass':>6} {'Findings':>9}"
    print()
    print(header)
    print("-" * len(header))
    for r in results.results:
        print(
            f"{r.eval_name:<30} {r.score:>6.2f} {r.max_score:>6.2f} "
            f"{'yes' if r.passed else 'NO':>6} {len(r.findings):>9}"
        )
    print("-" * len(header))
    print(
        f"{'TOTAL':<30} {results.total_score():>6.2f} "
        f"{results.total_max_score():>6.2f} "
        f"{results.passed_count():>6}/{len(results.results)}"
    )
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Run evals against a research-agent case directory.",
    )
    parser.add_argument(
        "case_path",
        help="Path to the case directory (e.g. samples/case_001)",
    )
    parser.add_argument(
        "--only",
        default=None,
        help="Comma-separated list of eval names to run (e.g. ae-6,ae-1)",
    )

    args = parser.parse_args(argv)

    only = [s.strip() for s in args.only.split(",")] if args.only else None
    results = run_evals(args.case_path, only=only)

    _print_summary(results)

    results.save(args.case_path)
    print(f"Results written to {args.case_path}/eval_results.json")


if __name__ == "__main__":
    main()
