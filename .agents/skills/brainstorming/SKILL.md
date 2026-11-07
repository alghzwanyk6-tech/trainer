---
name: brainstorming
description: >-
  Use this skill before starting any non-trivial feature, refactor, or architecture change.
  It guides the agent to ask clarifying questions, explore design alternatives, and produce
  an approved specification before writing any code.
---

# Brainstorming & Design Specification

This skill enforces a structured inquiry process to refine ambiguous requirements into clear technical specifications. Inspired by the `obra/superpowers` engineering methodology.

## Core Principles
1. **Never Assume**: If requirements, UI expectations, or edge cases are unclear, clarify them first.
2. **Explore Alternatives**: Propose 2-3 viable architectural or implementation approaches with trade-offs.
3. **No Code Before Consensus**: Do not begin writing production code or tests until the approach and requirements are aligned.

## Workflow Steps

### 1. Requirements Gathering
- Identify the problem statement and technical goals.
- Check existing project files, configurations, and architecture constraints.
- Formulate specific, actionable questions to resolve ambiguities.

### 2. Solution Design
- Outline the proposed architecture or feature flow.
- List affected files and dependencies.
- Address edge cases, error handling, performance implications, and security boundaries.

### 3. Deliverable: Design Spec
Summarize the proposal into a concise design specification for approval:
- **Objective**: What is being built.
- **Components Changed**: List of modules.
- **Verification Plan**: How the solution will be proven working.
