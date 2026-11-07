---
name: verification-and-review
description: >-
  Use this skill before declaring any task complete or committing changes.
  It reviews code quality, documentation integrity, and regression test status.
---

# Verification and Review

Ensure all changes meet the highest software engineering quality and safety standards before completion.

## Verification Checklist

1. **Test Suite Integrity**:
   - Run the full test suite: `pytest`
   - All tests must pass with zero failures or unexpected skips.

2. **Code Cleanliness & Style**:
   - No leftover temporary print statements or debug flags.
   - Type annotations preserved and updated.
   - Existing comments and docstrings preserved unless deliberately updated.

3. **Scope & Safety Adherence**:
   - No unauthorized automation or policy violations.
   - Preview-only mode and safety guards remain intact.

4. **Documentation**:
   - Update `handoff.md` or relevant documentation when features or states change.
   - Summarize changes concisely for the user.
