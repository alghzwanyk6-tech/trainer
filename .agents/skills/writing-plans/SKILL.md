---
name: writing-plans
description: >-
  Use this skill when preparing to execute a feature, refactor, or complex task.
  It decomposes work into bite-sized, atomic steps with explicit verification criteria.
---

# Writing Implementation Plans

This skill breaks down an approved design specification into small, executable, verifiable tasks.

## Key Rules
- **Atomic Tasks**: Each step represents 2-5 minutes of work.
- **Explicit Paths**: Always specify exact file paths and line ranges where applicable.
- **Verification First**: Every step must have a concrete command or test to verify success.
- **Fail-Fast**: Stop and debug immediately if any verification step fails.

## Plan Structure Template

```markdown
### Task 1: [Short Task Title]
- **Target File(s)**: `path/to/file.py`
- **Action**: Detailed description of what to add, edit, or remove.
- **Verification**: Exact test command (e.g., `pytest tests/test_target.py -k test_feature`).
- **Expected Outcome**: Pass/fail condition or specific log output.
```

## Plan Execution Discipline
1. Execute one step at a time.
2. Run the verification command.
3. Only proceed to the next step once the current step passes.
