# Merge & Cleanup

Merge a sprint feature branch directly into main and clean up the worktree.

Takes a feature name/slug or branch name as input. **Optional argument:** `keep-artifacts` — when provided, the exploration doc and tracking doc are preserved instead of being deleted during cleanup.

## Stage 1: Identify Branch & Validate

1. Determine the branch name from the input:
   - If given a slug, look for branch matching `*<slug>*`
   - If given a full branch name, use it directly
2. Verify the branch exists locally:
   ```bash
   git branch | grep "<branch>"
   ```
   If not found, **STOP** — the branch doesn't exist.
3. Check if there's a worktree for this feature:
   ```bash
   git worktree list | grep "<slug>"
   ```
4. If a worktree exists, check for uncommitted work:
   ```bash
   git -C /tmp/sra-<slug> status --porcelain
   git -C /tmp/sra-<slug> log main..HEAD --oneline
   ```
   If there are uncommitted changes or commits not yet merged, **STOP** — tell the user the branch has in-progress work.

## Stage 2: Merge into main

1. From the main working tree:
   ```bash
   cd <PROJECT_ROOT>
   git checkout main
   git merge <branch> --no-ff -m "<type>: <concise feature description>"
   ```
2. If merge fails due to conflicts:
   - Report the conflicting files
   - **STOP** — tell the user to resolve conflicts manually

## Stage 3: Cleanup

1. Remove the worktree if it exists:
   ```bash
   git worktree remove "/tmp/sra-<slug>" --force
   ```
2. Delete the local branch:
   ```bash
   git branch -d <branch>
   ```
3. Clean up any stale worktree-agent branches:
   ```bash
   git branch | grep "worktree-agent-" | grep -v '^\*' | xargs -r git branch -D
   ```
4. Delete the tracking doc and explore doc — **skip this step if `keep-artifacts` was provided**:
   ```bash
   rm -f docs/TRACKING_<slug>.md docs/EXPLORE_<slug>.md
   git add docs/
   git commit -m "chore: remove tracking and explore docs for <slug>"
   ```
5. Push main to origin:
   ```bash
   TOKEN=$(gh auth token) && git remote set-url origin "https://${TOKEN}@github.com/<owner>/<repo>.git"
   git push origin main
   ```

## Rules

- All git operations run from the main working tree (`<PROJECT_ROOT>`), not the worktree
- Feature branches are merged directly into `main` — no GitHub PRs
- If the branch has uncommitted work, refuse to proceed
- If merge conflicts occur, stop and report — do not force merge
- If any stage fails, stop and report the error — do not retry blindly
- Use `gh auth token` for the push token (not `.claude/.env`)
