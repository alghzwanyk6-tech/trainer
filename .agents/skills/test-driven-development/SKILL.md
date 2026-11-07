---
name: test-driven-development
description: >-
  Use this skill when writing new features, fixing bugs, or refactoring code.
  It strictly enforces the RED-GREEN-REFACTOR cycle with pytest.
---

# Test-Driven Development (TDD)

This skill enforces strict engineering discipline: write failing tests before writing production code.

## The TDD Cycle

### 1. RED (Write Failing Test)
- Create or update a test reproducing the requirement or bug in `tests/test_*.py`.
- Run pytest: `pytest tests/test_target.py`
- Confirm that the test fails for the expected reason (e.g., `AttributeError`, `AssertionError`, not syntax error).

### 2. GREEN (Implement Minimal Code)
- Write the minimum amount of production code required to make the test pass.
- Do not add speculative features or unnecessary complexity.
- Re-run the test to confirm it passes.

### 3. REFACTOR (Clean Up)
- Clean up duplication, improve readability, and adhere to typing/naming conventions.
- Re-run the entire test suite (`pytest`) to ensure zero regressions across all tests.

## Rules
- Never write production code without an accompanying test.
- If a test passes before writing code, the test is invalid or redundant.
- Keep tests isolated, fast, and deterministic (mock heavy I/O, UI, and external capture).
