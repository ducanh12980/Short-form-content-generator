# Pull request checklist

Use in PR descriptions for agent- or human-authored changes.

## Summary

- [ ] One-line summary of **why** (not just what changed)
- [ ] Linked issue or task ID from [current-tasks.md](current-tasks.md) if applicable

## Code

- [ ] Change is scoped to the task — no unrelated refactors
- [ ] Matches [code conventions](../conventions/code-style.md)
- [ ] No secrets, API keys, or `.env` files committed

## Verification

- [ ] Tests pass (or N/A with reason)
- [ ] Lint / format pass (or N/A with reason)
- [ ] Manual test steps documented below (for UI or media output)

### Manual test steps

```
1.
2.
```

## Docs

- [ ] `AGENTS.md` or `docs/` updated if setup, commands, or architecture changed
- [ ] ADR added if architectural decision was made

## Security / content

- [ ] No unsanitized user content in logs
- [ ] External API calls documented if new ([security guidelines](../security/guidelines.md))
