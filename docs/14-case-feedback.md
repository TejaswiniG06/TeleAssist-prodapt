# Saved cases and confirmed outcomes

Explain the feedback loop this way: a generated response is a suggestion; an agent records what actually happened; an editor reviews the outcome before it becomes historical evidence.

## Workflow

1. Prepare a response in Support Assistant and choose **Save pending case**. Saving is explicit, not automatic. The backend masks the complaint, observations, draft and classification before storing a case in `runtime/cases.sqlite3`.
2. Open **Saved Cases**. Record actions actually performed, a resolved/not-resolved outcome and how that outcome was confirmed. Do not copy proposed actions unless they were actually performed. Confirm the report before submitting.
3. An editor reviews the complaint, actual actions and reported outcome, supplies corrected product/category, applicability, a title and rationale, and approves or rejects publication.
4. Approval uses the existing background ingestion worker. Searches retain the previous index until replacement indexes publish successfully. A reviewed resolved case becomes resolved history; an unsuccessful case becomes unresolved history and cannot supply successful resolution steps.
5. Refresh to inspect the publication state and source version. Published history is available to future searches without restarting the API. New complaint clears the form but does not delete saved cases.

No additional LLM calls are made by saving, outcome capture or review. The original draft and its cited IDs/versions remain a separate snapshot. Publication uses actual recorded actions and human-reviewed conditions, not the draft's suggestions or inferred symptoms.

## API and modules

| Endpoint | Permission |
| --- | --- |
| POST /cases | Agent: explicitly save a pending draft snapshot |
| GET /cases, GET /cases/{id} | Agent: inspect shared prototype cases |
| POST /cases/{id}/outcome | Agent: record an actual outcome with expected case revision |
| POST /admin/cases/{id}/review | Editor: reject or submit reviewed evidence for indexing |

`cases.py` defines schemas and a small SQLite ledger. `case_api.py` coordinates access, revisions and the existing catalog. The SQLite module is part of Python's standard library: no external database service or API is needed. API factories use in-memory SQLite by default for isolated tests; executable single-process and retrieval services persist to the ignored runtime database.

In split mode, case operations use the dashboard's editor/evidence service address, including agent save/outcome requests. Address routing does not grant editor permissions: each backend endpoint enforces its own role. Case storage lives with the retrieval service, which publishes evidence. Requests to /resolve remain independent and never send saved-case or conversation history to the LLM.

## Reliability and boundaries

- Saving has a client request ID: repeating an identical save after a lost response returns the same case. Reusing the ID with different content returns 409.
- Updates require expected case revisions; stale edits and changes to publishing/published cases return 409. New evidence publication also requires the current index version.
- States are pending, outcome_recorded, publishing, published and rejected. A rejected case can receive a corrected outcome and be reviewed again.
- SQLite transactions persist case revisions/events. Existing atomic evidence persistence stores published history. There is no distributed transaction between them: case reads reconcile publication against durable source version 1.
- Failed/interrupted unpublished jobs return the case to outcome_recorded with an explicit retry message. If evidence committed before the case acknowledgement, durable source history restores the published state on inspection. Unique job IDs avoid accidental links to unrelated jobs after restart.
- Agent reports and editor review are human attestations, not independent proof that an operational fix worked. Evidence is labelled reviewed_internal, not provider-approved KB.
- Operational cases/history are ignored by Git. Pattern masking is limited; the current shared agent/editor keys give a shared workspace, not per-user ownership or enterprise audit identity. Retention/deletion controls, encryption, per-user access and durable distributed jobs remain deployment requirements.

The frozen 487-record evaluation remains a base-corpus checkpoint. Operationally published cases change live counts and retrieval results; do not rewrite the frozen benchmark scores to imply they measured an expanded live corpus.

## Verified checkpoint

78 behavioural tests and dependency checks pass. Eight case backend tests cover masking, idempotent saves, permissions, stale revisions, actual-action requirements, rejected/unresolved outcomes, failed-index retries and two restart reconciliation paths. Two dashboard tests cover the empty state and the full save → actual outcome → editor review → future search path against the real API. No provider calls are made by that workflow test.

`python smoke_case_feedback.py` uses a fictional case, temporary databases/catalog files and the real local embedding model. Its pending case is absent from retrieval; after review/publication, the source appears at rank 1 in keyword, semantic and hybrid searches within the broadband resolved-history pool. Case and evidence survive a reconstructed application. The initial corpus contains 487 records, with no live evidence modified and zero LLM calls. This is a functional publication check, not a relevance benchmark.
