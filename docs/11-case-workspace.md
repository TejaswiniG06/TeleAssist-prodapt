# Case workspace dashboard

Start the backend and dashboard in separate terminals from the repository folder:

```powershell
./.venv/Scripts/python.exe -m uvicorn api:app --host 127.0.0.1 --port 8000
```

```powershell
./.venv/Scripts/python.exe -m streamlit run dashboard.py
```

Open http://127.0.0.1:8501. The original lightweight interface remains available on port 8000. Both call the same backend; the dashboard does not import retrieval, masking, classification or provider modules. Streamlit's native [top navigation](https://docs.streamlit.io/develop/api-reference/navigation/st.navigation) provides the Case workspace layout without a custom component framework.

## Screens and live data

| Screen | Backend operations |
| --- | --- |
| Support Assistant | POST /resolve; GET exact /sources/id?version=N |
| Saved Cases | POST/GET /cases; POST actual outcome; editor-only review through existing background ingestion |
| Evidence Explorer | POST /search with mode/product/type filters; inspect current or exact source versions |
| Knowledge & Topics | Editor GET /admin/topics and /admin/audit; POST topic review and /admin/ingest; GET job status; GET taxonomy |
| System Health | GET /health, /ready and editor /admin/metrics |

There are no demo role pickers, sample cases, fabricated topic proposals, fixed corpus counts or test-score tiles. Counts/readiness/latency/errors/outcomes come from the APIs. Empty queues, missing measurements, absent credentials and unavailable services are shown explicitly. Evaluation results remain documented checkpoints, separate from operational health.

Each response request sends only the current complaint and observations. Session state retains the current displayed result and form fields for rerenders, but never sends conversation history. New complaint clears the fields/result without deleting saved cases. Changing the application key clears preceding identity's displayed results. Explicit Save pending case sends a draft snapshot to masked backend SQLite storage; actual actions/outcomes require a separate report and editor review before entering retrieval. See [case feedback](14-case-feedback.md). The dashboard does not save keys/results to its own files or browser local storage. Customer/evidence strings use plain text rendering, not executable HTML. The Streamlit server necessarily receives the application key; it never reads the provider .env or sends the Gemini key to the browser.

The Resolution search query selector chooses enriched (default) or raw. Enriched appends the already computed classification's technical terms for retrieval; it adds no model call or conversation memory. The displayed result reports the chosen mode. Evidence Explorer retains raw, key-free retrieval; it does not silently classify each search.

The application access field accepts a backend agent/editor key. Local mode allows key-free agent requests; editor features require a configured TELEASSIST_EDITOR_KEY in the backend and a successful /admin/access check. The server still enforces each privileged endpoint. No dropdown can grant authority. Shared keys are a prototype control, not enterprise user identity. Keep this local dashboard bound to localhost; public deployment needs identity, TLS and session/retention controls.

Evidence updates accept the backend's strict IngestRequest schema rather than duplicating every validator in the UI. Review the batch and expected versions, submit once, and inspect the returned job ID. A network timeout does not prove the server rejected an update; check job/audit state before resubmitting. Topic approval also requires a rationale and explicit review confirmation.

## Optional split services

In the dashboard terminal, set deployment addresses before startup:

```powershell
$env:TELEASSIST_API_URL='http://127.0.0.1:8002'
$env:TELEASSIST_EDITOR_URL='http://127.0.0.1:8001'
./.venv/Scripts/python.exe -m streamlit run dashboard.py
```

Resolution/search/citation reads use the API address. Catalog/topic/metrics editor requests use the editor address (retrieval). The existing split-service backend configuration remains as documented in [service deployment](09-service-deployment.md). Credentials must be accepted by both relevant services. The UI uses bounded HTTP timeouts and displays failures without inventing successful results.

Case save/list/outcome/review requests also use the retrieval/editor service address. That address setting does not grant editor permissions: agents can save/report outcomes, while review/publication is enforced as editor-only by the backend. Saved Cases lists the latest 100 cases in the shared prototype workspace. It is persistent operational storage, not chatbot memory.

## Explain the code

dashboard.py builds four screens and displays results. dashboard_client.py sends HTTP requests and translates connection/auth/version failures into readable messages. FastAPI remains responsible for decisions and permission checks. Native Streamlit widgets keep the interface small and maintainable. Layout follows the reviewed Case workspace's top navigation and complaint/review columns; it is not a pixel-exact reproduction of the HTML preview.

## Verified checkpoint

55 behavioural tests pass with Streamlit 1.65.0 and pip check reports no broken requirements. Dashboard tests cover application credentials, exact source versions, separate editor routing, independent submissions, clearing, identity changes and API failures. An editor-screen integration test runs against the actual FastAPI application, submits an evidence batch to an isolated in-memory catalog, confirms publication and observes the live count/version change. It does not modify the working catalog or use provider credentials. UI testing follows Streamlit's [AppTest interface](https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest).

A headless browser checked the running dashboard on port 8501 against the real local API on port 8000: keyword evidence appeared, the configured provider returned a cited resolution draft, New complaint cleared inputs, and 360px rendering had no page errors or horizontal overflow. Local editor screens require an editor key; none is automatically created or bundled. Broader independent applicability/urgency evaluation remains pending as documented separately.
