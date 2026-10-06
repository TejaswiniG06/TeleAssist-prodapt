# Case workspace dashboard

For a visual, task-by-task guide, see the [screenshot walkthrough](17-dashboard-walkthrough.md). The dashboard uses real FastAPI requests; UI role choice never grants backend permissions.

## Start the current application

From the repository root, after completing the README setup:

```powershell
./.venv/Scripts/python.exe start.py
```

Open http://127.0.0.1:8501/. The recommended launcher starts retrieval on 8001, resolution on 8002 and Streamlit on 8501. It warms the local semantic model and configures the dashboard addresses. `--mode combined` retains the API on 8000 and the original lightweight interface. See [service deployment](09-service-deployment.md) for manual process configuration.

## Screens and backend operations

| Screen | What the user does | API operations |
| --- | --- | --- |
| Support Assistant | Describe a complaint, prepare a checked draft, answer clarification, inspect sources or explicitly save a case | POST /resolve, POST /search, exact GET /sources reads, POST /cases |
| Saved Cases | Open a saved case, report actual actions/outcome, review and publish with editor permissions | GET /cases, POST outcome and editor review |
| Evidence Explorer | Search by words, meaning or both; filter service/type; inspect cited versions | POST /search, GET /sources |
| Editor Evidence | Add/update/retire through readable forms; check jobs and publication activity | POST /admin/ingest, GET jobs/audit |
| Topics | Review grouped weak-match complaints and browse current categories | GET topics/taxonomy, POST topic review |
| Health | Inspect live service readiness, response times, errors and optional diagnostics | GET /health, /ready, /admin/metrics |

## Complaint and clarification flow

Examples are collapsed and only fill the form. Device selection is optional and appends context to observations; it does not force a product classification. Action tags add only actions actually performed with unknown outcomes until the agent supplies results. Advanced search retains raw and enriched modes; query enrichment reuses classification output without a separate rewriting call.

Prepare troubleshooting draft sends the complaint and observations to /resolve. Search supporting sources only retrieves evidence and does not generate a draft. A clarification response displays each unique question once with an answer field beneath it. Continue combines answered question/answer pairs with the retained original complaint and observations, then calls the same API. Empty answers do not trigger a request. There is no conversational model memory; each request contains its own current-case context.

Source cards preserve exact cited versions. Pending drafts are not evidence. Explicit saving creates a masked SQLite case snapshot; actual actions, outcome confirmation and editor review precede publication. Only reviewed published records enter future retrieval. Retiring a source removes it from current search while preserving earlier cited versions; deleting saved cases remains future work.

The main response is labelled Suggested resolution. The AI selects source actions rather than writing arbitrary troubleshooting instructions; recognized attempted actions are excluded from the selection options and checked again on return. Steps appear once, with their source references. Why step N was suggested expands the quote and applicability details; Cited sources groups complete records. Search cards display Relevance rank: N of M for the returned results; numeric retrieval scores remain in Match details. These are not percentages of answer correctness.

## Access and presentation

Local agents can leave the application key blank. Knowledge Editor requires a configured editor key and /admin/access verification. `.env.example` contains the public local-demo key `editor`; replace it before shared deployment. Application keys are separate from the Gemini provider key. Advanced access uses an explicit Apply access key action; changing identity clears displayed case state.

Light/Dark appearance is session-level presentation. Readable forms, badges and tables replace raw editor JSON; developer batch import and health diagnostics remain collapsed. Topic categories can be filtered. Backend data supplies counts, job state, health and case outcomes; empty data is shown honestly. Customer and evidence strings render as plain text.

Open a source by ID explains how to inspect an exact record/version. Advanced batch import — for developers is optional; editors use Add, Update or Retire for ordinary changes. Health labels fallback counts as historical activity rather than a live AI outage. Its readable reasons, reset-on-restart counters and bounded 256-request timing window preserve the existing monitoring behaviour.

The Streamlit server receives the entered application key, but the launcher strips provider credentials from its environment and the dashboard does not read the provider .env. Keys are not stored in browser local storage or dashboard files. Public deployment still needs appropriate identity, TLS and storage/retention controls.

## Code and verification

`frontend/app.py` owns role/navigation, `frontend/views/` contains screens, `frontend/client.py` handles HTTP errors, and components/styles provide shared presentation. Backend algorithms and permissions remain outside the UI.

The current regression suite covers case persistence/publication, clarification continuation, application-role checks, exact source versions, stale updates, service outages and both themes. Separate HTTP smoke checks use real local embeddings and temporary storage. See the README for the current test count. Independent answer applicability and urgency evaluation remain open.
