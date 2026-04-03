# Improvements: Tuning, Configuration & Correctness

No new evals or features. This doc covers what to fix, tune, and tighten in what already exists or is planned.

---

## 1. Claim Extraction Is Called Redundantly

**Problem:** AE-4, AE-5, and AE-7 all independently call `extract_claims()`, which makes an LLM call each time. For a single case, that's 3x the same expensive LLM operation returning (ideally) the same claims.

**Fix:** Cache claim extraction results per case run. Options:
- **Runner-level caching:** The eval runner calls `extract_claims()` once, passes the result into each eval function via an optional `claims` parameter. Evals that receive pre-extracted claims skip the LLM call.
- **Disk cache:** Write `claims.json` to the case folder after first extraction; subsequent evals load from disk.

**Impact:** ~3x reduction in LLM calls for Track B evals. Also eliminates non-determinism where the same report produces different claim lists across evals.

---

## 2. AE-6 Scoring Is Binary — Should Be a Ratio

**Problem:** AE-6 returns `score=1.0` if all citations match, `score=0.0` if any single one doesn't. A report with 29/30 valid citations scores the same as one with 0/30.

**Fix:** Score as `matched_citations / total_citations`. Keep `passed` as a threshold check (e.g., `score >= 1.0` for zero tolerance, or `score >= 0.95` for near-perfect). This makes AE-6 consistent with AE-4, AE-5, and AE-7 which all use ratio-based scoring.

---

## 3. Pass/Fail Thresholds Are Inconsistent and Hardcoded

**Problem:** Each eval has its own hardcoded pass threshold buried in the code:
- AE-6: `passed = score == 1.0`
- AE-5, AE-7: `passed = score >= 0.9`
- AE-4: unclear

No central place to configure or override thresholds.

**Fix:** Define thresholds in a central config (e.g., `evals/config.py` or env vars):
```python
PASS_THRESHOLDS = {
    "ae-1": 0.7,
    "ae-4": 0.8,
    "ae-5": 0.9,
    "ae-6": 1.0,
    "ae-7": 0.85,
}
```
Allow CLI override: `--threshold ae-6=0.95`. This makes tuning thresholds a config change, not a code change.

---

## 4. Numeric Citation Matching Relies on a Fragile Assumption

**Problem:** For `[N]` citations, AE-6 assumes table row `N-1` corresponds to reference `[N]`. If the table is re-sorted, has header rows mid-file, or papers are numbered differently, matching silently breaks.

**Fix:**
- **Short-term:** Add a validation step: after matching, log the citation's reference number and the matched paper's title so a human can spot-check. Include this in the eval output as an `info`-severity finding.
- **Medium-term:** Support a `references` section parser that builds an explicit `[N] → paper title` mapping from the report's References section. Use that mapping for numeric citation resolution instead of positional indexing.

---

## 5. AE-7 Grounding Check Will Hit Token Limits on Real Data

**Problem:** AE-7 sends each claim + ALL paper summaries (title, abstract, focus columns) to the LLM. The exploration doc notes the sample table has 98 rows. On real agent runs with 30+ papers and full abstracts, each AE-7 LLM call could be 10K+ tokens of context — multiplied by every claim in the report.

**Fix:**
- **Truncate abstracts:** Cap at 300 chars per paper in the grounding prompt. The LLM only needs enough to judge relevance, not full text.
- **Pre-filter papers:** Before sending to the LLM, do a lightweight keyword/embedding similarity pass to narrow down candidate papers per claim (top 5-10 instead of all). This is a significant cost and latency win.
- **Batch claims:** Group 3-5 claims per LLM call instead of one-at-a-time. The LLM can evaluate multiple claims against the same paper set in a single prompt.

---

## 6. No LLM Response Validation Beyond JSON Parsing

**Problem:** `LLMJudge` retries on malformed JSON (good), but doesn't validate that the response conforms to the expected schema. If the LLM returns `{"verdict": "yes"}` instead of `{"verdict": "supports"}`, the eval silently gets garbage.

**Fix:** After JSON parsing, validate that returned values are within the expected enum sets. For rubric-based judging, `judge_with_rubric` already checks dimension values — extend this pattern to `judge()` by validating response keys exist and values are in allowed sets. Log and retry on schema violations (count toward the 2-retry budget).

---

## 7. No Reproducibility Metadata in Results

**Problem:** `eval_results.json` contains scores and findings but not:
- Which LLM model was used
- Timestamp of the run
- Software version / git commit
- LLM temperature / parameters

Two runs on the same case can produce different results with no way to trace why.

**Fix:** Add metadata to `CaseResults`:
```python
@dataclass
class RunMetadata:
    timestamp: str          # ISO 8601
    model: str              # EVAL_LLM_MODEL value
    git_commit: str | None  # subprocess.run(["git", "rev-parse", "HEAD"])
    eval_version: str       # package version or "dev"
```
This is a small addition to the result schema that pays for itself in debugging.

---

## 8. Claim Extractor Has No Ground-Truth Validation

**Problem:** The exploration doc explicitly flags this: "LLM response is trusted. No validation against original text." The claim extractor can hallucinate claims that don't exist in the report, and those phantom claims would inflate uncited/ungrounded findings.

**Fix:** After extraction, verify each claim's `text` field appears in (or fuzzy-matches against) the report. Drop claims that can't be located. This is a cheap string-matching step that catches the most damaging LLM hallucination mode.

---

## 9. Sample Data Doesn't Actually Test What It Claims

**Problem:** The SPRINT_FOUNDATION_PARSERS doc says case_001 has three intentional defects: fabricated reference, uncited claim, wrong citation. But the integration exploration reveals:
- The "fabricated reference" (`[6]` / Tanaka et al.) is in the References section but never inline-cited, so AE-6 doesn't catch it
- AE-6 returns `score=1.0, passed=True` on the sample — the planted defect is invisible

This means the sample data doesn't actually validate that AE-6 works.

**Fix:**
- **Add a real fabricated citation** to the report body — a `[31]` or `(Fake et al., 2099)` that genuinely doesn't exist in the table. AE-6 should catch this and return `score < 1.0`.
- Keep the existing Tanaka reference as a test case for a future "unused references" check.
- Ensure each intentional defect is actually caught by the eval it's designed for. Otherwise the test data gives false confidence.

---

## 10. No Parallel Execution in the Eval Runner

**Problem:** The runner executes evals sequentially. Track A evals (AE-1, AE-2, AE-3) are independent of Track B evals (AE-4, AE-5, AE-7). Even within tracks, some evals are independent.

**Fix:** Use `asyncio.gather()` or `concurrent.futures.ThreadPoolExecutor` to run independent evals in parallel. Since most evals are LLM-bound (not CPU-bound), threading works fine. The runner already isolates errors per-eval, so this is low-risk.

**Impact:** Running 7 evals with 3-5 LLM calls each goes from ~30s sequential to ~10s parallel (assuming 2-3s per LLM call).

---

## 11. Fuzzy Matching Threshold (0.6) Is Uncalibrated

**Problem:** `get_paper_by_title()` uses a 0.6 similarity threshold with `difflib.SequenceMatcher`. This was chosen as "a starting default" with a note to adjust later. No calibration has been done.

**Fix:**
- Run the matcher against sample data with various thresholds (0.5, 0.6, 0.7, 0.8) and log matches vs misses.
- The requirements already include `rapidfuzz` — consider switching to it for better matching quality and performance. `SequenceMatcher` is known to be inconsistent on short strings.
- Make the threshold a parameter on the eval runner (env var or CLI flag) so it can be tuned without code changes.

---

## 12. `match_citation_to_table()` Returns First Match Only

**Problem:** When matching author-year citations to table rows, the function returns the first row where any cited surname appears AND year matches. If multiple papers share an author and year, the wrong paper could silently be matched.

**Fix:**
- If multiple rows match, return all of them (or flag the ambiguity as a warning).
- For AE-5, use the full set of matching papers and let the LLM judge which one actually supports the claim.
- At minimum, log when multiple matches exist so ambiguous cases are visible.

---

## 13. LLM Judge Has No Cost Tracking

**Problem:** No visibility into how many tokens/dollars each eval run consumes. As the suite grows (7 evals x multiple LLM calls each), cost could spike without awareness.

**Fix:** Track token usage from the OpenAI response object (`response.usage.prompt_tokens`, `response.usage.completion_tokens`). Aggregate per-eval and per-run. Include in `RunMetadata` or print in the CLI summary table.

---

## 14. Tech Stack Inconsistency: difflib vs rapidfuzz

**Problem:** `requirements.txt` includes `rapidfuzz>=3.0.0`, but the parsers use `difflib.SequenceMatcher` (stdlib). The SPRINT_FOUNDATION_PARSERS doc explicitly chose stdlib to "keep the foundation lightweight." Now both are in the project.

**Fix:** Pick one:
- If `rapidfuzz` is in requirements anyway, use it everywhere (better quality, faster).
- If minimizing deps matters, remove `rapidfuzz` from requirements and stick with `difflib`.

Don't carry both.

---

## Priority Order

| # | Improvement | Effort | Impact |
|---|------------|--------|--------|
| 9 | Fix sample data to actually test defects | Small | High — false confidence in test suite |
| 1 | Cache claim extraction across evals | Small | High — 3x LLM cost reduction |
| 2 | AE-6 ratio scoring | Trivial | Medium — scoring consistency |
| 3 | Central pass thresholds | Small | Medium — tuning without code changes |
| 8 | Claim extractor validation | Small | High — prevents hallucinated findings |
| 6 | LLM response schema validation | Small | Medium — prevents silent garbage |
| 5 | AE-7 token optimization | Medium | High — blocks real-world scaling |
| 7 | Reproducibility metadata | Small | Medium — debugging and trust |
| 4 | Numeric citation resolver | Medium | Medium — correctness on real data |
| 14 | Pick difflib or rapidfuzz | Trivial | Low — cleanup |
| 12 | Multi-match handling | Small | Medium — correctness edge case |
| 11 | Calibrate fuzzy threshold | Small | Low-Medium — data-dependent |
| 10 | Parallel eval execution | Medium | Medium — latency only |
| 13 | LLM cost tracking | Small | Low-Medium — observability |
