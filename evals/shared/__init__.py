"""evals.shared — shared utilities consumed by all eval modules."""

from evals.shared.loader import CaseData, load_case
from evals.shared.citation_parser import Citation, extract_citations, match_citation_to_table
from evals.shared.table_parser import PaperRecord, parse_table, get_paper_by_title
from evals.shared.results import Finding, EvalResult, CaseResults
from evals.shared.llm_judge import LLMJudge
from evals.shared.claim_extractor import Claim, extract_claims

__all__ = [
    "CaseData",
    "load_case",
    "Citation",
    "extract_citations",
    "match_citation_to_table",
    "PaperRecord",
    "parse_table",
    "get_paper_by_title",
    "Finding",
    "EvalResult",
    "CaseResults",
    "LLMJudge",
    "Claim",
    "extract_claims",
]
