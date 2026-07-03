---
name: agent-task
description: >-
  Pick up, track, and complete work using docs/workflow/current-tasks.md.
  Use when starting a multi-step task, coordinating agent sessions, or handoff.
---

# Agent task workflow

## Start work

1. Read `AGENTS.md` and `docs/workflow/agentic-workflow.md`.
2. Open `docs/workflow/current-tasks.md`.
3. Move the task from **Backlog** to **In progress** with date and owner (`agent` or name).
4. Read only the docs linked from the task or `AGENTS.md` directory guide.

## During work

- One concern per change set; avoid unrelated edits.
- If blocked, move task to **Blocked** with reason; ask user if decision needed.

## Finish work

1. Verify tests/lint or document why skipped.
2. Move task to **Done** with completion date and one-line note.
3. Update architecture docs or ADR if behavior or stack changed.
4. Use `docs/workflow/pr-checklist.md` for PR description when opening a PR.
