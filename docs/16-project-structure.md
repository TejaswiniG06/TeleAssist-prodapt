# Project structure and module guide

The dashboard sends HTTP requests; the backend owns classification, retrieval, evidence updates and permission checks. Modules are grouped by responsibility.

```text
TeleAssist-prodapt/
  start.py                   Local process launcher
  dashboard.py               Streamlit entry point
  api.py                     Combined compatibility entry point
  retrieval_api.py           Retrieval service entry point
  resolution_api.py          Resolution service entry point
  teleassist/
    services/                HTTP routes and request schemas
    retrieval/               BM25, semantic/hybrid search and query building
    resolution/              Classification, state checks, selection and provider client
    ingestion/               Versioned catalog updates and index publication
    cases/                   Transactional SQLite case store
    common/                  Access, masking, metrics and project paths
    topics.py                Topic grouping and reviewed taxonomy
  frontend/
    app.py                   Role selection and navigation
    client.py                HTTP client
    components.py            Shared rendering and source navigation
    styles.css               Light/dark styling and animations
    views/                   Agent, cases, evidence, topics and health
  scripts/
    data/                    Download, preparation and corpus tools
    evaluation/              Retrieval, classification and load measurements
    smoke/                   Model and HTTP integration checks
  tests/                     Behaviour, UI and failure regression tests
  data/                      Evidence, frozen queries and evaluation summaries
  docs/                      Setup, design, evaluation and user guides
  web/                       Original lightweight interface
  runtime/                   Ignored SQLite storage, state, caches and logs
  scratch/                   Ignored optional downloads and local diagnostics
```

## Complaint path

1. `frontend/views/agent.py` collects the complaint, observations and clarification answers.
2. `frontend/client.py` sends HTTP requests to the configured API.
3. `teleassist/services/resolution.py` validates inputs and calls the resolver.
4. `teleassist/common/privacy.py` masks supported identifiers before processing.
5. `teleassist/resolution/pipeline.py` classifies, excludes recognized attempted actions and checks selected steps. `state.py` handles common prerequisite questions and answered-state tracking; `llm.py` handles the provider, pacing and bounded retries.
6. `teleassist/retrieval/` constructs the search query and ranks evidence with BM25, local embeddings and RRF.
7. The response returns cited steps, clarification or escalation to the dashboard. Saving is a separate explicit operation.

## Evidence and case ownership

`teleassist/ingestion/catalog.py` validates editor batches, builds replacement indexes and publishes versions. `teleassist/cases/store.py` stores pending cases and actual reported outcomes in SQLite. Reviewed cases enter retrieval through the same ingestion path. `teleassist/topics.py` groups weak-match complaints for taxonomy review.

The retrieval service owns catalog, case and topic storage. Resolution calls it over HTTP. The combined compatibility service reuses the same modules. `teleassist/common/paths.py` anchors data and runtime paths to the repository root.

## Running and checking

```powershell
./.venv/Scripts/python.exe start.py
./.venv/Scripts/python.exe -m unittest discover -s tests -q
./.venv/Scripts/python.exe -m scripts.smoke.smoke_split
./.venv/Scripts/python.exe -m scripts.evaluation.evaluate_query_enrichment --replay-frozen-classifications
```

The final command replays historical classification predictions; it does not evaluate the updated classifier. Use explicit refresh for new predictions. See the [README](../README.md), [deployment guide](09-service-deployment.md) and [evaluation guide](13-query-enrichment.md) for setup and limits.

`requirements.txt` contains compatible ranges; `requirements-lock.txt` pins the tested environment. Runtime storage and provider/application keys are excluded from Git. The README reports the current test count. Functional tests and integration checks do not establish real-world answer accuracy.
