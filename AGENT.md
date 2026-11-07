# AGENT.md - Token Optimization & Direct Execution Rules

## 1. Token Conservation & Scoping Rules
- **Targeted Scope Only**: Do NOT scan the workspace tree, search directories recursively, or inspect files unless explicitly named in the prompt.
- **No Unsolicited File Reading**: Never open or read background documentation, skill directories (`.agents/skills/`), or secondary files without a direct user request.
- **Minimal Output**: Provide direct, ready-to-use code blocks or diffs only. Omit conversational filler, explanations of basic concepts, and status overviews unless requested.
- **No Unrequested Refactoring**: Modify only the specific functions, lines, or files targeted by the user. Do not perform speculative edits or general codebase refactoring.

---

## 2. Execution Protocol
- **Single-Turn Delivery**: Implement the requested change directly in the first response without breaking simple tasks into multi-turn brainstorming or planning phases.
- **Exact Edits**: When editing, return only the modified section or file content needed to apply the change, avoiding re-printing unmodified files.
- **Tool Discipline**: Do not execute background diagnostic commands, linters, or test suites unless the user explicitly asks to run them.

---

## 3. Active Workspace Reference
When modifying code, operate strictly on the specified file within:
- `desktop_app.py`
- `config.py`
- `bot/` (`worker.py`, `controller.py`, `vision.py`, `capture.py`)
- `tests/`