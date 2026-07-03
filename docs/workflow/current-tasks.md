# Current tasks

Living task board for agent and human work. Agents: update this file when starting or finishing tasks.

## In progress

| ID | Task | Owner | Started | Notes |
|----|------|-------|---------|-------|
| — | — | — | — | — |

## Backlog

| ID | Task | Priority | Notes |
|----|------|----------|-------|
| T004 | Caption render stage (consume MVP payload) | High | Next phase after MVP |
| T005 | B-roll + acoustic mix wiring | Medium | Uses existing core modules |
| T003 | Scaffold project structure and CI | Medium | pytest in place; add GitHub Actions |
| T006 | TTS reliability (retry / line-by-line synth) | Low | Optional hardening for long Vietnamese scripts |

## Blocked

| ID | Task | Blocker |
|----|------|---------|
| — | — | — |

## Done

| ID | Task | Completed | Notes |
|----|------|-----------|-------|
| T000 | Set up docs/ and agentic workflow | 2026-07-03 | AGENTS.md, docs/, .cursor/rules |
| **MVP** | **MVP orchestrator — script → tokens → TTS → payload** | **2026-07-03** | **Complete.** Entry: `orchestrator_mvp.py`. Outputs: `output/narration.mp3`, `output/pipeline_payload.json`. Vietnamese LLM prompts + `vi-VN-HoaiMyNeural`. Tests: `pytest tests/test_orchestrator_mvp.py`. ADR 0001. |
| T001 | MVP orchestrator (LLM + TTS + payload) | 2026-07-03 | See **MVP** row |
| T002 | Core content models for MVP payload | 2026-07-03 | `topic`, `raw_script`, `tokens`, `audio` in `pipeline_payload.json` |
