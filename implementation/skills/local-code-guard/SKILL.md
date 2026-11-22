---
name: local-code-guard
description: Apply global local quality gates when creating, modifying, refactoring or generating code in any project. Fix executable-check failures before completion; ordinary prose does not require code linting.
---

# Local code guard

- The executable gate is `$CODEX_HOME/code-guard/hook.py`. Trusted user-level Hooks invoke it; a Skill alone is not enforcement. Verify actual runtime results before claiming activation.
- Follow the global recovery workflow. Register the real target root using tool `workdir` before edits; do not hide writes to another root inside shell absolute paths or `cd`.
- Rule values live in `scan.mjs`, `python_metrics.py` and `policies.json` beside the gate. Read the relevant implementation as needed; do not copy numeric limits into instructions.
- Default enforcement covers only new or worsened diagnostics attributable to this chat’s tool windows, against its pre-edit state. Other chats’ pending failures and unchanged historical documents are not adopted.
- Baseline evidence persists; never reset state, suppress checks or raise limits to pass. Checker maintenance requires explicit authorization and regression validation.
- PostToolUse checks synchronously; Stop/SubagentStop recheck this chat’s changes across registered roots, including committed code. Continue the same chat to retain its unresolved failures.
- Historical audit is optional: set CODEX_GUARD_SCOPE=history only for an explicitly requested audit against the preserved baseline. A lint pass does not establish business correctness.
- JS/TS, JSX/TSX and Python have adapters. Python uses AST length and branch checks rather than ESLint's identical metric. Recognized unsupported source types block when changed; unknown extensions are not certified.
- Project retired-module contracts belong in `policies.json` under `retiredModules`, with exact root, old module and replacement. Static require/import references are supported; computed imports and mere code age are not proof of retirement.
- Dependency environments, Git metadata and checker state are outside the source scan. Missing checkers, baselines or trust must be reported as blockers. Respect user interruptions; never describe an unexecuted gate as passed.

For persistent instruction changes, use [instruction maintenance](../instruction-maintenance/SKILL.md).
