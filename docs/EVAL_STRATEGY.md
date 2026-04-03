# Eval Strategy

## Core Insight: Self-Referential Evaluation

Most evals **do not require a manually curated golden dataset**. The agent's own artifacts serve as cross-references for each other:

- **Report claims** can be verified against **source papers** (from table.csv)
- **Report sections** can be checked against **planning doc** (todo.md)
- **Citations in report** can be cross-referenced against **retrieved paper list** (table.csv)
- **Planning doc** can be compared against **user query** (query.txt)

Only **system block evals** (retrieval recall, reranking) need golden data — and these are deferred to a later phase.

---

## Artifacts Per Case

Each eval case = one run of the research agent. Stored in `samples/case_NNN/`:

| File | What It Is | Produced By |
|---|---|---|
| `query.txt` | Raw user query | User |
| `todo.md` | Planning doc with research scope, headings, focus areas | Agent Step 1 |
| `table.csv` | Extraction table: papers x focus criteria columns | Agent Step 5 |
| `report.md` | Final generated report with citations | Agent Step 6 |

---

## Eval Catalog

### Artifact Evals

Evaluate the quality of output artifacts. These measure *whether* the output is good.

> **Note:** System Block Evals (SB-1 through SB-4) are documented separately in [SYSTEM_BLOCK_EVAL_STRATEGY.md](SYSTEM_BLOCK_EVAL_STRATEGY.md).

#### AE-1: Planning Faithfulness
- **Artifact:** `todo.md`
- **Type:** LLM-judge
- **Needs golden data:** No
- **Input:** `query.txt` + `todo.md`
- **Measures:** Does the plan correctly capture (a) research question, (b) purpose/intent, (c) appropriate scope/exploratory areas?
- **How:** LLM-judge scores on 3 dimensions with a rubric:
  - Research question captured? (yes/partial/no)
  - Purpose identified? (survey / comparison / deep-dive / other)
  - Scope appropriate? (too broad / just right / too narrow)
- **Output:** Structured scores + reasoning

#### AE-2: Section Coverage
- **Artifact:** `report.md`
- **Type:** Script + LLM
- **Needs golden data:** No
- **Input:** `todo.md` + `report.md`
- **Measures:** Does the report address all exploratory areas from the plan?
- **How:**
  1. Script: Extract section headings from both docs
  2. LLM: Map plan sections → report sections, identify gaps
- **Output:** Coverage percentage + list of missing/underexplored areas

#### AE-3: Analysis Depth
- **Artifact:** `report.md`
- **Type:** LLM-judge (rubric)
- **Needs golden data:** No
- **Input:** `query.txt` + `report.md`
- **Measures:** Is depth appropriate for the query purpose?
- **How:** LLM classifies query purpose, then evaluates depth against purpose-specific rubric:
  - Survey → expects breadth (many papers, brief each)
  - Comparison → expects cross-paper synthesis
  - Deep-dive → expects detailed analysis of fewer papers
- **Output:** Purpose classification + depth score (1-5) + reasoning

#### AE-4: Citation Completeness
- **Artifact:** `report.md`
- **Type:** LLM
- **Needs golden data:** No
- **Input:** `report.md`
- **Measures:** What fraction of factual claims have citations?
- **How:**
  1. LLM parses report, identifies all factual/empirical claims
  2. Checks each claim for an inline citation
  3. Computes: `cited_claims / total_claims`
- **Output:** Completeness ratio + list of uncited claims

#### AE-5: Citation Correctness
- **Artifact:** `report.md`
- **Type:** LLM
- **Needs golden data:** No (uses source papers from table.csv)
- **Input:** `report.md` + `table.csv` + source paper content
- **Measures:** Does the cited paper actually support the claim?
- **How:** For each (claim, citation) pair:
  1. Extract the claim
  2. Look up cited paper in table.csv
  3. LLM judges: supports / contradicts / unrelated
- **Output:** Correctness ratio + list of incorrect citations with reasoning
- **Note:** Requires access to paper abstracts/content. If table.csv includes abstracts, this works directly. Otherwise, may need supplementary paper data.

#### AE-6: Fabricated References
- **Artifact:** `report.md`
- **Type:** Script (deterministic)
- **Needs golden data:** No
- **Input:** `report.md` + `table.csv`
- **Measures:** Do all cited papers in the report exist in the retrieved set?
- **How:** Extract all paper references from report, cross-check against paper list in table.csv
- **Output:** Pass/fail + list of fabricated references
- **Priority:** Build first — trivial to implement, catches a critical failure mode

#### AE-7: Grounding Check
- **Artifact:** `report.md`
- **Type:** LLM
- **Needs golden data:** No (uses source papers)
- **Input:** `report.md` + source paper content
- **Measures:** Are all claims traceable to source papers? (hallucination detection)
- **How:** For each claim in the report (cited or not):
  1. Search source papers for supporting evidence
  2. Classify: grounded / partially grounded / ungrounded
- **Output:** Grounding rate + list of ungrounded claims
- **Distinction from AE-5:** AE-5 checks if the *specific cited paper* supports the claim. AE-7 checks if *any* source paper supports the claim. A claim can fail AE-5 (wrong citation) but pass AE-7 (content is grounded, just cited wrong paper).

---

## One-Off Run Workflow

To evaluate a new case:

```bash
# 1. Create a case folder and drop in artifacts
mkdir samples/case_003
# Place: query.txt, todo.md, table.csv, report.md

# 2. Run all evals on that case
python -m evals.run samples/case_003/

# 3. View results
cat samples/case_003/eval_results.json
```

The runner will:
1. Auto-discover all four artifacts in the case folder
2. Run all applicable evals (skip any that lack required inputs)
3. Produce a structured results file with scores and findings

---

## Build Order

### Phase 1a: Foundation — Parsers + LLM Infrastructure (2 parallel sessions)

Two sessions with zero cross-dependencies, running simultaneously.

**Session: Data + Parsers** ([sprint doc](SPRINT_FOUNDATION_PARSERS.md))

| Component | What It Does | Used By |
|---|---|---|
| Sample test data | `samples/case_001/` with intentional errors for evals to catch | All evals (testing) |
| Artifact loader | Load + validate case folder | All evals |
| Citation parser | Extract paper references from report.md | AE-4, AE-5, AE-6 |
| Table parser | Parse table.csv into structured paper records | AE-5, AE-6 |

**Session: LLM Infrastructure** ([sprint doc](SPRINT_FOUNDATION_LLM.md))

| Component | What It Does | Used By |
|---|---|---|
| LLM judge base | Prompt scaffolding, structured output, rubric runner | AE-1, AE-2, AE-3, AE-4, AE-5, AE-7 |
| Result schema | EvalResult, Finding, CaseResults dataclasses + JSON serialization | All evals |
| Claim extractor | Identify factual/empirical claims in report.md (uses LLM judge) | AE-4, AE-5, AE-7 |

### Phase 1b: Foundation — Integration (1 session, after 1a)

Wires everything together. ([sprint doc](SPRINT_FOUNDATION_INTEGRATION.md))

| Component | What It Does | Depends On |
|---|---|---|
| Package init files | `__init__.py` for all packages | All Phase 1a modules |
| Eval runner + CLI | Registry, runner, `python -m evals.run` CLI | Loader, result schema |
| AE-6 (Fabricated Refs) | First eval — validates parsers end-to-end | Citation parser, table parser, loader |
| requirements.txt | Pin all dependencies | All modules |

### Phase 2: Eval Tracks (2 parallel sessions, after 1b)

Two independent tracks, one session each. No cross-dependencies.

**Track A: Plan + Structure** ([sprint doc](SPRINT_TRACK_A.md)) — "Did the report follow the plan?"

| Eval | Input Artifacts | Shared Utilities |
|---|---|---|
| AE-1 (Planning Faithfulness) | query.txt, todo.md | LLM judge base |
| AE-2 (Section Coverage) | todo.md, report.md | LLM judge base |
| AE-3 (Analysis Depth) | query.txt, report.md | LLM judge base |

**Track B: Claim-Level** ([sprint doc](SPRINT_TRACK_B.md)) — "Are the claims real and cited right?"

| Eval | Input Artifacts | Shared Utilities |
|---|---|---|
| AE-4 (Citation Completeness) | report.md | Claim extractor, citation parser, LLM judge base |
| AE-5 (Citation Correctness) | report.md, table.csv | Claim extractor, citation parser, table parser, LLM judge base |
| AE-7 (Grounding Check) | report.md, source papers | Claim extractor, LLM judge base |

### Dependency Graph

```
Phase 1a (parallel)          Phase 1b           Phase 2 (parallel)
┌──────────────────┐
│ Sample data       │
│ Artifact loader   │──┐
│ Citation parser   │──┤
│ Table parser      │──┤
└──────────────────┘  │
                       ├──→ Integration ──┬──→ Track A: AE-1, AE-2, AE-3
┌──────────────────┐  │     (runner,     │
│ LLM judge base   │──┤      AE-6,      ├──→ Track B: AE-4, AE-5, AE-7
│ Result schema    │──┤      CLI)        │
│ Claim extractor  │──┘                  │
└──────────────────┘
```

---

## Golden Data Strategy

**Short answer: not needed for artifact evals. Build it incrementally.**

- All artifact eval phases use only the agent's own artifacts + LLM-as-judge. No manual curation.
- LLM-judge calibration: periodically sample eval outputs and manually verify. If the LLM judge drifts, adjust prompts/rubrics. This is lightweight — spot-check 5-10 cases, not annotate hundreds.
- For golden data needs of system block evals, see [SYSTEM_BLOCK_EVAL_STRATEGY.md](SYSTEM_BLOCK_EVAL_STRATEGY.md).
