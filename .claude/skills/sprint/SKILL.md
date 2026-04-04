# Sprint — Full Feature Lifecycle

Pick a feature from the local tracking docs, implement it end-to-end, merge to main, and clean up. Runs the full pipeline with a single checkpoint after plan creation.

**Optional argument:** `keep-artifacts` — when provided, the tracking doc (`TRACKING_<slug>.md`) is preserved after merge instead of being deleted during cleanup.

This skill orchestrates sprint agents. Each stage is delegated to a specialized agent with an optimal model tier. Do NOT duplicate agent logic — launch them via the Agent tool and let them do their job.

## Stage 1: Pick Feature

1. Read `docs/DEVELOPMENT_PLAN.md` to identify available features/phases.
2. Present the list to the user and ask which feature to pick (or auto-pick the next incomplete one if user said "auto").
3. Read the full feature description to understand scope.

## Stage 2: Git Setup (Worktree)

1. Fetch latest main (no checkout needed):
   ```
   git fetch origin main
   ```
2. Determine the worktree path and branch name:
   ```
   WORKTREE_DIR="/tmp/sra-<feature-slug>"
   BRANCH="<feature-slug>"
   ```
3. Check if worktree already exists (rerun after failure):
   ```
   git worktree list | grep "sra-<feature-slug>"
   ```
   - If it exists, `cd` into the existing worktree directory and skip to Stage 3
4. Create worktree with feature branch from main:
   ```
   git worktree add "$WORKTREE_DIR" -b "$BRANCH" origin/main
   ```
5. `cd` into the worktree — **ALL subsequent work happens here**:
   ```
   cd "$WORKTREE_DIR"
   ```
6. Install dependencies if needed (worktree is a fresh checkout):
   ```
   pip install -r requirements.txt  # if exists
   ```

## Stage 3: Explore

Launch the **sprint-explore** agent (haiku) using the Agent tool:
- `subagent_type: "sprint-explore"`
- In the prompt, provide:
  - The full feature description
  - Path to relevant module doc (if referenced)
  - The worktree path so it can read existing code
- The agent will return a scope summary

Proceed directly to planning — no checkpoint.

## Stage 4: Plan (with checkpoint)

1. Launch the **sprint-plan** agent (opus) using the Agent tool:
   - `subagent_type: "sprint-plan"`
   - In the prompt, provide:
     - The feature description
     - The tracking doc path: `<worktree>/docs/TRACKING_<feature-slug>.md`
     - The worktree path
   - The agent will produce the tracking document
2. **CHECKPOINT — Present the plan to the user and wait for approval before continuing.**
   - Show the plan summary
   - Ask: "Plan ready. Proceed with implementation?"
   - If user says no or requests changes, revise the plan and ask again
   - Do NOT proceed to Stage 5 until user confirms

## Stage 5: Execute

Launch the **sprint-execute** agent (sonnet) using the Agent tool:
- `subagent_type: "sprint-execute"`
- In the prompt, provide:
  - The tracking doc path: `docs/TRACKING_<feature-slug>.md`
  - The worktree path
  - The feature description for context

## Stage 6: Build Check

Verify the code works before review.

1. **Python checks:**
   ```
   cd backend && python -m py_compile app/main.py  # check key files
   ```
   Also run tests if they exist:
   ```
   python -m pytest --tb=short  # if tests exist
   ```

2. **Frontend check** (if frontend files were changed):
   - Verify HTML/JS files are syntactically valid

3. If any build errors are found, fix them before proceeding to review.

## Stage 7: Review

1. Launch the **sprint-review** agent (opus) using the Agent tool:
   - `subagent_type: "sprint-review"`
   - In the prompt, provide:
     - The worktree path
     - A summary of what was implemented
     - List of changed files (from `git diff --name-only origin/main`)
     - The tracking doc path: `<worktree>/docs/TRACKING_<feature-slug>.md`
2. Auto-fix any CRITICAL or HIGH issues found, then re-run build check if fixes were applied

## Stage 8: Commit & Push

1. Commit all changes:
   ```
   git add -A
   git commit -m "<type>: <concise description from feature title>"
   ```
   Use conventional commit types: `feat`, `fix`, `refactor`, `docs`, `chore`
3. Push the branch to origin:
   ```
   TOKEN=$(gh auth token) && git remote set-url origin "https://${TOKEN}@github.com/<owner>/<repo>.git"
   git push -u origin <branch>
   ```
4. Report: "Branch `<branch>` pushed. Ready for merge."

## Stage 9: Merge & Cleanup

Invoke the `/pr-merge` skill with the feature slug. If the `keep-artifacts` argument was provided, pass it through:
   ```
   /pr-merge <feature-slug>                    # default: deletes tracking doc
   /pr-merge <feature-slug> keep-artifacts     # preserves tracking doc
   ```

   This handles:
   1. Merging the branch directly into `main` via `git merge`
   2. Removing the worktree and deleting the branch
   3. Cleaning up tracking doc (unless `keep-artifacts` was specified)
   4. Pushing `main` to origin

After `/pr-merge` completes, report final status: "<feature-slug> merged to main."

## Rules

- Never proceed past a checkpoint without explicit user approval
- If any stage fails, stop and report the error — do not retry blindly
- Keep the tracking doc updated throughout execution
- Do NOT reimplement logic from agents — launch them and let them do their job
- If a worktree already exists for the feature, reuse it instead of recreating
