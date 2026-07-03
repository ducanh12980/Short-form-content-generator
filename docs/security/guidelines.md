# Security guidelines

Applies to agents and humans working on short-form content generation (APIs, user content, exports).

## Secrets

- Store secrets in environment variables or a secret manager — never in git.
- Add `.env`, `*.pem`, credentials JSON to `.gitignore`.
- Rotate keys if accidentally exposed; do not "fix" by removing from the latest commit only.

## API keys (LLM, TTS, media cloud)

- Load from env at runtime; validate presence with clear startup errors.
- Do not log request bodies that may contain user prompts or PII.
- Rate-limit and retry with backoff; avoid unbounded spend in loops.

## User / generated content

- Treat prompts and scripts as potentially sensitive unless explicitly public.
- Do not send content to third-party APIs without documented purpose in ADR or architecture.
- Sanitize filenames and paths for exported media (no raw user strings in shell commands).

## Shell and media commands

- Never build ffmpeg or shell commands by string-concatenating untrusted input.
- Use argument arrays or validated allowlists for codecs, paths, and durations.

## Dependencies

- Review new packages for maintenance and known issues.
- Do not auto-fix security audit findings without human review on critical paths.

## Reporting

If an agent discovers exposed credentials in the repo, stop and inform the user immediately — do not commit fixes that spread the secret further.
