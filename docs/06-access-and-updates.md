# Access and evidence updates

An agent can search and prepare drafts; an editor can also change evidence. Keys map to those two roles. They are application credentials, separate from the Gemini provider key, and are never committed.

`AUTH_MODE=local` keeps the localhost reviewer demo usable without credentials. Anonymous users have agent permissions only. Editor access always needs `TELEASSIST_EDITOR_KEY`. In `required` mode, both agent and editor keys must be present and different or configuration fails. An absent/invalid request key returns 401; a valid agent key used on editor routes returns 403. `/admin/access` verifies editor access.

Supply `X-API-Key` in API requests, use the Swagger Authorize control, or enter the agent key in the browser access field. The browser holds it only in memory. Raw source links opened in a new tab cannot carry this custom header in required mode; “View evidence” fetches with the header. Clear removes the key with the form.

This is role-based access for a local prototype, not full user identity management. Public hosting requires required mode behind HTTPS and per-user identity/OIDC, rotation/revocation and shared quotas. Public health and the interface shell contain no evidence text or credentials. Bind local mode to 127.0.0.1.

## Validated background updates

An editor submits `POST /admin/ingest` with the current `expected_index_version` and a batch of changes. Each change contains `expected_version` (0 for a new source) and a complete evidence record. Swagger documents the strict fields. Resolved tickets require historical steps and explicit outcome evidence; unverified public records cannot be promoted into verified history. Text is pattern-masked before persistence. Suspicious instructions and incoherent record types are rejected. These checks validate structure and provenance labels, not whether a claimed outcome happened in reality.

The endpoint returns a job ID and HTTP 202. Poll `/admin/jobs/{job_id}`. The single background worker builds replacement keyword and semantic indexes while readers use the previous snapshot. It persists validated overrides/history atomically, then swaps the active snapshot. Failed preparation preserves previous evidence. Stale versions and overlapping jobs return 409. Unchanged embeddings reuse the content/model cache. Retire a record by submitting it with `status=retired`; new searches exclude it. Historical versions remain inspectable through `/sources/{id}?version=N`.

`GET /admin/audit` records role, UTC time, source IDs/versions/status and index version, without complaints or keys. Updated evidence and audit/history live in ignored `runtime/evidence_state.json`. Do not commit operational data. Restarts restore published updates. To undo content, retrieve a historical version and submit its content as a new revision using the current expected versions.

The prototype supports one retrieval/catalog writer and one ingestion worker. The resolution service runs separately and calls retrieval over HTTP. Job statuses are in memory; interrupted unpublished jobs are not durable/replayed. Atomic file replacement protects the published state, but this is not a multi-host transaction system. Multiple processes need shared storage, coordination, a persistent queue and per-user audit identity. Pattern masking is still not comprehensive anonymization. Keep the original datasets unchanged; updates are an overlay.
