# Update Documentation Task

You are updating documentation after code changes.

## 1. Identify Changes
- Check git diff or recent commits for modified files
- Identify which features/modules were changed
- Note any new files, deleted files, or renamed files

## 2. Verify Current Implementation
**CRITICAL**: DO NOT trust existing documentation. Read the actual code.

For each changed file:
- Read the current implementation
- Understand actual behavior (not documented behavior)
- Note any discrepancies with existing docs

## 3. Update Relevant Documentation

- **CHANGELOG.md**: Add entry under "Unreleased" section
  - Use categories: Added, Changed, Fixed, Security, Removed
  - Be concise, user-facing language

- **docs/DECISIONS.md**: If any key product or architectural decisions were made during this feature, append an entry:
  ```markdown
  ## YYYY-MM-DD — Decision Title
  **Context:** What prompted this decision
  **Decision:** What was decided
  **Reasoning:** Why this choice over alternatives
  **Alternatives considered:** What else was evaluated
  ```
  - Only add entries for non-trivial decisions (technology choices, architecture patterns, tradeoffs, scope decisions)
  - Skip if the feature was pure implementation with no decision points

## 4. Documentation Style Rules

✅ **Concise** - Sacrifice grammar for brevity
✅ **Practical** - Examples over theory
✅ **Accurate** - Code verified, not assumed
✅ **Current** - Matches actual implementation

❌ No enterprise fluff
❌ No outdated information
❌ No assumptions without verification

## 5. Ask if Uncertain

If you're unsure about intent behind a change or user-facing impact, **ask the user** - don't guess.