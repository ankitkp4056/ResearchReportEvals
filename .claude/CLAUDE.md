# CLAUDE.md — Research Report Evals

## Project

Evaluation suite for a Scientific Research Agent (separate repo). The agent generates research reports from user queries with citations. This repo builds evals to measure quality of both the agent's pipeline stages and its output artifacts.

**This repo is eval-only — no agent code lives here.**

---

## System Under Evaluation

The research agent pipeline:

```
Step 1: User Query → Planning Doc (ToDo.md)
Step 2: Generate optimized search queries for Google Scholar, PubMed, Scispace
Step 3: Execute searches, retrieve papers with relevancy scores
Step 4: Rerank papers, filter by threshold (max X papers)
Step 5: Extract focus criteria columns from each paper → final table (CSV)
Step 6: Generate report (MD) from final table
```

Artifacts produced per run: `query.txt`, `todo.md`, `table.csv`, `report.md`

---

## Eval Buckets

### Bucket 1: System Block Evals
Evaluate whether each pipeline stage did its job correctly.

| Eval | Stage | Type | What It Measures |
|---|---|---|---|
| Search Query Quality | Step 2 | LLM-judge | Are generated queries well-formed, DB-appropriate, semantically aligned with user query? |
| Retrieval Recall | Step 3 | Script (needs gold set) | Do known-relevant papers appear in results? Recall@K, Precision@K |
| Reranking Correctness | Step 4 | Script + Manual | Are top-ranked papers actually the most relevant? NDCG against human judgments |
| Focus Criteria Extraction | Step 5 | LLM + Manual | Are the right columns identified? Are extracted values correct per paper? |

### Bucket 2: Artifact Evals
Evaluate the quality of output artifacts.

| Eval | Artifact | Type | What It Measures |
|---|---|---|---|
| Planning Faithfulness | ToDo.md | LLM-judge | Does the plan capture research question, purpose, and appropriate scope from the query? |
| Section Coverage | Report | Script + LLM | Does the report address all exploratory areas from the plan? |
| Analysis Depth | Report | LLM-judge (rubric) | Is depth appropriate for the query purpose (survey vs comparison vs deep-dive)? |
| Citation Completeness | Report | LLM | What fraction of factual claims have citations? |
| Citation Correctness | Report | LLM | Does the cited paper actually support the claim? |
| Fabricated References | Report | Script | Do all cited papers exist in the retrieved set? |
| Grounding Check | Report | LLM | Are all claims traceable to source papers? (hallucination detection) |
| Numerical Accuracy | Report | LLM + Script | Are numbers/statistics correctly reproduced from sources? |
| Table Completeness | Table (CSV) | Script + LLM | Are all focus columns populated? Are values accurate per paper? |

---

## File Structure

```
samples/                    — test cases (one folder per agent run)
  case_001/
    query.txt               — raw user query
    todo.md                 — planning doc produced by agent
    table.csv               — final extraction table
    report.md               — generated report
  case_002/
    ...

evals/                      — eval implementations
  system/                   — Bucket 1: pipeline block evals
  artifact/                 — Bucket 2: output artifact evals
  shared/                   — shared utilities (LLM judge helpers, parsers)

golden/                     — gold-standard references for benchmarking
  case_001/
    expected_queries.json   — known-good search queries (optional)
    relevant_papers.json    — known-relevant papers for recall measurement
    annotations.json        — human judgments (claim-level, section-level)

docs/
  DEVELOPMENT_PLAN.md       — phased build plan
  DECISIONS.md              — product/design decisions

requirements.txt
CHANGELOG.md
```

---

## Code Conventions

- Python 3.11+
- Virtual environment (`venv/`)
- Dependencies in `requirements.txt`
- Type hints encouraged
- Eval scripts should be runnable standalone: `python -m evals.artifact.citation_correctness samples/case_001/`

---

## Branching & Commits

`main` is the only long-lived branch. Commit directly for sequential work.

```bash
git add <specific files>
git commit -m "<concise description>"
```
