---
name: subagent-driven-development
description: >-
  Use this skill when tackling large, multi-faceted tasks that benefit from
  isolated subagents for research, implementation, or review.
---

# Subagent-Driven Development

Organize complex workflows across focused, single-responsibility subagents to keep context clean and prevent hallucinations.

## Subagent Roles

1. **Researcher**: Read-only exploration of files, documentation, and external references.
2. **Implementer**: Performs code edits and writes tests for an isolated module according to an approved plan.
3. **Reviewer**: Evaluates diffs against requirements, style guides, and test coverage before merging.

## Rules
- Give each subagent a single, clearly bounded prompt.
- Check subagent outputs before incorporating them into the main context.
- Keep the parent context uncluttered.
