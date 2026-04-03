# System Block Eval Strategy

Evaluate whether each pipeline stage did its job. These diagnose *where* things break.

> See [EVAL_STRATEGY.md](EVAL_STRATEGY.md) for artifact evals and overall strategy.

---

## Eval Catalog

### SB-1: Search Query Quality
- **Stage:** Step 2 (query generation)
- **Type:** LLM-judge
- **Needs golden data:** No
- **Input:** `query.txt` + generated search queries (if captured)
- **Measures:** Are queries well-formed, DB-appropriate (MeSH for PubMed, keywords for GS), semantically aligned with user intent?
- **How:** LLM rates each query on relevance, specificity, and DB-appropriateness
- **Status:** Deferred — requires capturing intermediate search queries from the agent

### SB-2: Retrieval Recall
- **Stage:** Step 3-4 (search + rerank)
- **Type:** Script
- **Needs golden data:** Yes (known-relevant papers per query)
- **Input:** `query.txt` + `table.csv` + golden relevant papers list
- **Measures:** Recall@K — do known-relevant papers appear in the final set?
- **How:** Compare retrieved paper list against golden set, compute recall/precision
- **Status:** Deferred — needs manually curated golden paper lists

### SB-3: Reranking Correctness
- **Stage:** Step 4 (rerank)
- **Type:** Script + manual
- **Needs golden data:** Yes (human relevance judgments)
- **Input:** Retrieved papers with scores + human relevance ratings
- **Measures:** NDCG — are top-ranked papers actually the most relevant?
- **Status:** Deferred — needs human relevance annotations

### SB-4: Focus Criteria Extraction
- **Stage:** Step 5 (table building)
- **Type:** LLM-judge
- **Needs golden data:** No (LLM verifies against source papers)
- **Input:** `query.txt` + `todo.md` + `table.csv`
- **Measures:** (a) Are the right columns identified from the query? (b) Are extracted values accurate per paper?
- **How:** LLM checks if columns align with query intent, then spot-checks cell values against paper abstracts/content

---

## Build Order

| Phase | Evals | Rationale |
|---|---|---|
| **Phase 1** | SB-4 (Extraction), SB-1 (Query Quality) | Don't need golden data |
| **Phase 2** | SB-2 (Retrieval), SB-3 (Reranking) | Requires golden datasets — build when enough cases exist |

---

## Golden Data Strategy

SB-1 and SB-4 use the agent's own artifacts + LLM-as-judge. No manual curation needed.

SB-2 and SB-3 need golden paper lists and human relevance judgments per query. Strategy: as you run evals on cases and manually review results, tag "known-good" paper lists in `golden/case_NNN/relevant_papers.json`. Over time, this accumulates naturally.
