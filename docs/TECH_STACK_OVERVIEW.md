# Tech Stack Overview — Eval Strategy

## What This Project Does

This repo evaluates a **Scientific Research Agent** that lives in a separate repo. That agent takes a user query (e.g., "Compare CBT vs DBT for treatment-resistant depression"), searches academic databases, retrieves papers, and generates a research report with citations.

Each agent run produces four artifacts:

```
query.txt   →  the user's research question
todo.md     →  the agent's planning doc (scope, sections, focus areas)
table.csv   →  structured paper data (title, authors, year, DOI, abstract, extracted metrics)
report.md   →  the final research report with inline citations
```

Our job: build automated evals that measure whether those artifacts are any good.

---

## The Key Insight: Self-Referential Evaluation

We don't need a manually curated "golden dataset" for most evals. The agent's own artifacts cross-check each other:

- **Report claims** verified against **source papers** (from table.csv)
- **Report sections** checked against **planning doc** (todo.md)
- **Citations in report** cross-referenced against **paper list** (table.csv)
- **Planning doc** compared against **user query** (query.txt)

This means most evals are either pure script logic or LLM-as-judge — no human annotation pipeline required.

---

## Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────┐
│                     CLI / Eval Runner                        │
│            python -m evals.run samples/case_001/             │
│                                                              │
│  ┌─────────────────────────┐  ┌────────────────────────────┐ │
│  │   Track A (Plan Evals)  │  │  Track B (Claim Evals)     │ │
│  │  AE-1 Plan Faithfulness │  │  AE-4 Citation Completeness│ │
│  │  AE-2 Section Coverage  │  │  AE-5 Citation Correctness │ │
│  │  AE-3 Analysis Depth    │  │  AE-6 Fabricated References│ │
│  └────────┬────────────────┘  │  AE-7 Grounding Check      │ │
│           │                   └──────────┬─────────────────┘ │
│           └──────────┬───────────────────┘                   │
│                      ▼                                       │
│  ┌───────────────────────────────────────────────────────┐   │
│  │              Shared Utilities (evals/shared/)          │   │
│  │                                                        │   │
│  │  ┌──────────────┐  ┌───────────────┐  ┌────────────┐  │   │
│  │  │  LLM Judge   │  │ Claim         │  │  Results   │  │   │
│  │  │  Base         │  │ Extractor     │  │  Schema    │  │   │
│  │  └──────────────┘  └───────────────┘  └────────────┘  │   │
│  │  ┌──────────────┐  ┌───────────────┐  ┌────────────┐  │   │
│  │  │  Citation    │  │ Table         │  │  Case      │  │   │
│  │  │  Parser       │  │ Parser        │  │  Loader    │  │   │
│  │  └──────────────┘  └───────────────┘  └────────────┘  │   │
│  └───────────────────────────────────────────────────────┘   │
│                      ▼                                       │
│  ┌───────────────────────────────────────────────────────┐   │
│  │              Sample Data (samples/case_NNN/)           │   │
│  │     query.txt  ·  todo.md  ·  table.csv  ·  report.md │   │
│  └───────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Layer 1: Shared Utilities (`evals/shared/`)

These are the building blocks every eval depends on. Split into two groups by whether they need an LLM.

### Pure Parsers (no LLM, no external deps)

| Module | Purpose | Key Interface |
|---|---|---|
| `loader.py` | Load a case folder into a structured `CaseData` object | `load_case(path) → CaseData` |
| `table_parser.py` | Parse table.csv into typed `PaperRecord` objects, fuzzy-match papers by title | `parse_table(csv_path) → list[PaperRecord]` |
| `citation_parser.py` | Extract citations from report text (handles `(Author, Year)`, `[Author, Year]`, `[1]` formats), match them to table rows | `extract_citations(report) → list[Citation]` |

**Tech:** Python stdlib only — `csv`, `re`, `dataclasses`, `pathlib`, `difflib.SequenceMatcher` for fuzzy matching.

### LLM Infrastructure (requires OpenAI-compatible API)

| Module | Purpose | Key Interface |
|---|---|---|
| `llm_judge.py` | Wrapper for LLM calls with structured JSON output and rubric scoring | `LLMJudge.judge(prompt, schema) → dict` |
| `claim_extractor.py` | Uses LLM to identify all factual/empirical claims in a report | `extract_claims(report, llm_judge) → list[Claim]` |
| `results.py` | Standardized eval output: `EvalResult`, `Finding`, `CaseResults` with JSON serialization | `CaseResults.save(path)` / `.load(path)` |

**Tech:** `openai` Python SDK pointed at any OpenAI-compatible API. Configured via environment variables:

```bash
EVAL_LLM_BASE_URL=https://api.openai.com/v1   # or any compatible endpoint
EVAL_LLM_API_KEY=sk-...
EVAL_LLM_MODEL=gpt-4o                          # or any model
```

The `LLMJudge` includes retry logic (up to 2 retries for malformed responses) and logs every prompt/response for debugging.

---

## Layer 2: The Seven Evals

### Track A — "Did the report follow the plan?" (Plan + Structure)

These evals only need `query.txt`, `todo.md`, and `report.md`. No table.csv dependency.

| Eval | What It Checks | Method |
|---|---|---|
| **AE-1: Planning Faithfulness** | Does todo.md capture the research question, purpose, and appropriate scope from query.txt? | LLM-judge scores 3 rubric dimensions |
| **AE-2: Section Coverage** | Does report.md address all topics from todo.md? | Script extracts headings, LLM maps plan→report sections |
| **AE-3: Analysis Depth** | Is the depth appropriate for the query type (survey vs comparison vs deep-dive)? | LLM classifies purpose, then scores against purpose-specific rubric |

### Track B — "Are the claims real and cited right?" (Claim-Level)

These evals consume claims + citations extracted by shared parsers.

| Eval | What It Checks | Method |
|---|---|---|
| **AE-4: Citation Completeness** | What fraction of factual claims have citations? | Claim extractor → check each for attached citation |
| **AE-5: Citation Correctness** | Does the cited paper actually support the claim? | Match citation to table, LLM judges: supports / contradicts / unrelated |
| **AE-6: Fabricated References** | Do all cited papers exist in the retrieved set? | **Pure script** — cross-check citations against table.csv |
| **AE-7: Grounding Check** | Are all claims traceable to any source paper? | LLM checks each claim against all paper summaries |

**Note:** AE-5 and AE-7 are complementary. A claim can fail AE-5 (wrong citation) but pass AE-7 (the content is grounded, just attributed to the wrong paper).

---

## Layer 3: Eval Runner + CLI (`evals/run.py`)

The runner ties everything together:

```bash
# Run all evals on a case
python -m evals.run samples/case_001/

# Run specific evals only
python -m evals.run samples/case_001/ --only ae-6,ae-1
```

How it works:
1. Each eval **registers** itself with a name and list of required artifacts (e.g., `["report", "table"]`)
2. Runner loads the case via `load_case()`, checks which artifacts exist
3. Runs all applicable evals (skips those missing required inputs)
4. Aggregates results into `CaseResults`, writes `eval_results.json` to the case folder
5. If one eval fails, logs the error and continues with remaining evals

---

## Build Order (Dependency Graph)

The system is built in phases, with parallelism where possible:

```
Phase 1a: Foundation (parallel)        Phase 1b: Integration       Phase 2: Evals (parallel)
┌──────────────────────────┐
│ Parsers Sprint            │
│  · Sample test data       │──┐
│  · Case loader            │  │
│  · Citation parser        │  │
│  · Table parser           │  │
└──────────────────────────┘  │
                               ├──→ Integration Sprint ──┬──→ Track A: AE-1, AE-2, AE-3
┌──────────────────────────┐  │     · Package inits      │
│ LLM Sprint                │  │     · Eval runner/CLI    │
│  · LLM judge base        │──┤     · AE-6 (first eval) ├──→ Track B: AE-4, AE-5, AE-7
│  · Result schema          │──┤     · requirements.txt   │
│  · Claim extractor        │──┘                          │
└──────────────────────────┘
```

**Current status:**
- Parsers sprint: **100% complete**
- LLM sprint: **0%** (next up)
- Integration sprint: **0%** (blocked on LLM sprint)
- Track A & B: **0%** (blocked on Integration)

---

## Runtime Dependencies

| Package | Why |
|---|---|
| `openai` | LLM client for judge calls (supports any OpenAI-compatible API) |
| Python stdlib | Everything else — `csv`, `re`, `dataclasses`, `pathlib`, `json`, `difflib` |

The parsers layer deliberately avoids external dependencies. Fuzzy matching uses `difflib.SequenceMatcher` (stdlib) rather than `thefuzz`/`rapidfuzz` to keep the foundation lightweight.

---

## Data Flow Example: Running AE-5 (Citation Correctness)

To see how the layers connect, here's what happens when AE-5 runs:

```
1. Runner calls load_case("samples/case_001/")
   → loader.py reads query.txt, todo.md, table.csv, report.md into CaseData

2. Claim extractor runs on report.md using LLM judge
   → LLM identifies all factual claims, returns list[Claim]
   → Each Claim has: text, section, citation (if any), is_numerical flag

3. For each claim with a citation:
   a. citation_parser.match_citation_to_table() matches it to a table.csv row
   b. table_parser builds a PaperRecord with title, abstract, focus columns
   c. LLM judge receives (claim_text, paper_record) and judges:
      supports / partially supports / contradicts / unrelated

4. Scores aggregated: correctness_ratio = avg(per_claim_scores)
   → EvalResult written with score + findings for each incorrect citation

5. Runner collects all EvalResults into CaseResults
   → Serialized to samples/case_001/eval_results.json
```

---

## Test Data Strategy

Sample data in `samples/case_001/` contains **intentional defects** for evals to catch:

| Defect | What | Which Eval Should Catch It |
|---|---|---|
| Fabricated reference | Citation to a paper not in table.csv | AE-6 |
| Uncited claim | A statistical claim with no citation | AE-4 |
| Wrong citation | Claim attributed to the wrong paper | AE-5 |

Each defect is marked with `<!-- DEFECT: ... -->` HTML comments so tests can locate them programmatically.
