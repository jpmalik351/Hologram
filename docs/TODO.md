# TODO Roadmap

## High Priority

- [ ] Make database persistence explicit in production:
  - Require PostgreSQL `DATABASE_URL` in deployed environments.
  - Avoid relying on SQLite fallback for environments where container/filesystem is ephemeral.
  - Validate startup with a clear error if DB is misconfigured.

- [ ] Add test coverage for critical routes:
  - `/api/login`, `/api/chat`, `/api/upload`, `/api/files`, `/api/files/<id>`
  - duplicate upload paths (`overwrite`, `keep_both`)

- [ ] Add character-scoped retrieval:
  - Include character metadata in uploaded chunks.
  - Filter retrieval by selected character to reduce cross-character bleed.

## Medium Priority

- [ ] Persist conversation history (optional product decision):
  - Current behavior is session-memory only.
  - Consider DB-backed sessions or conversation table.

- [ ] Improve observability:
  - request IDs
  - basic metrics for endpoint latency, error rates, token usage
  - structured logs export

- [ ] Add admin tooling for file operations:
  - bulk delete
  - re-index/re-embed
  - file download/preview

## Lower Priority

- [ ] Citation UX:
  - expose source chunks in chat responses
  - show filename/chunk references in UI

- [ ] Cost controls:
  - per-user quotas
  - budget alerts
  - model fallback policies

