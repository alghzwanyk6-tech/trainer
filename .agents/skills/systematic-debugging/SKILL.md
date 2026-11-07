---
name: systematic-debugging
description: >-
  Use this skill when an error, test failure, unexpected behavior, or regression occurs.
  It prevents random trial-and-error patching and guides root-cause analysis.
---

# Systematic Debugging

Avoid guessing or applying blind patches. Follow a hypothesis-driven debugging methodology.

## 4-Phase Debugging Process

### Phase 1: Problem Definition & Reproduction
- Capture the exact error traceback, log output, or unintended behavior.
- Create a minimal reproduction script or isolated test case that reliably reproduces the failure.

### Phase 2: Hypothesis Generation
- Formulate 1-3 testable hypotheses explaining *why* the bug occurs.
- Trace the data flow through inputs, state transitions, and outputs.

### Phase 3: Evidence Gathering & Isolation
- Add targeted logging, print statements, or debugger checkpoints.
- Inspect actual vs. expected values at key boundaries.
- Disprove or confirm hypotheses one by one using empirical data.

### Phase 4: Minimal Targeted Fix & Regression Test
- Apply the smallest fix addressing the confirmed root cause.
- Run the reproduction test to confirm it now passes.
- Run the full test suite (`pytest`) to guarantee zero regressions.
- Remove temporary debug logs.
