# Local microservice deployment

The recommended reviewer setup runs **two separate FastAPI services** and a Streamlit dashboard. No Docker installation is needed. Each backend has its own process, port, lifecycle and metrics; the resolution service calls retrieval over HTTP.

## One-command startup

From the repository folder, after installing requirements:

```powershell
./.venv/Scripts/python.exe start.py
```

| Process | Address | Owns |
| --- | --- | --- |
| Retrieval/evidence | http://127.0.0.1:8001/docs | Corpus, MiniLM, search, versioned sources, ingestion, case database, topics and editor actions |
| Resolution | http://127.0.0.1:8002/docs | Masking, classification, query enrichment, provider calls, attempted-action protection, citation checks and fallbacks |
| Dashboard | http://127.0.0.1:8501 | Role navigation, complaint entry and existing agent/editor workflows |

The launcher loads backend configuration from `.env`, checks authentication and available ports, starts retrieval, warms local semantic search without a provider call, starts resolution, then starts Streamlit with the correct API addresses. Provider credentials are removed from the dashboard child's environment. Press Ctrl+C to stop only these owned process trees; saved data remains on disk. Logs are written to ignored `runtime/logs`. On Windows, shutdown also stops the Python children of virtual-environment launchers. A child failure stops the remaining owned processes and exits with an error.

The first model download needs internet and can take longer than the 180-second warmup budget. Pre-download with `python -m scripts.smoke.smoke_services`, or use `python start.py --skip-warmup` for keyword-only startup; the first semantic query then loads the model. This option does not claim semantic readiness. Cold and warm response times differ.

## Authentication and routing

`AUTH_MODE=local` permits anonymous agent access only; editor actions require `TELEASSIST_EDITOR_KEY`. Required mode needs distinct agent and editor application keys. The launcher uses `TELEASSIST_AGENT_KEY` as the retrieval service credential unless `RETRIEVAL_API_KEY` is explicitly supplied. That credential must be accepted by retrieval. Never use the Gemini key as an application/service key. Resolution validates the user key, while retrieval validates the service credential on forwarded calls. Direct case/editor calls validate the user's key at retrieval.

The dashboard sends drafting, search and source inspection to resolution. Case saving, actual outcomes, evidence updates, topic review and editor verification go directly to retrieval. Health displays both services' metrics rather than losing resolution outcomes. The same application agent/editor keys should be configured on both services for the local dashboard; tests also cover different gateway and service credentials.

Resolution fetches one index version before searching each evidence tier. Publication between requests triggers a controlled retry/fallback, not mixed-version grounding. Exact source versions remain inspectable after retirement. Weak searches are captured by retrieval; resolution reports no-applicable-evidence complaints to its topic monitor through an authenticated, masked observation request. Topic-monitor transport failure does not invalidate a response. Editor approval is still required to change taxonomy.

## Storage and compatibility

Retrieval alone owns `runtime/cases.sqlite3`, `runtime/evidence_state.json` and `runtime/topic_state.json` in split mode. Existing combined-mode data is reused when switching modes; no migration or deletion is performed. `TELEASSIST_STATE_DIR` overrides this directory for isolated checks or separate installations. Downloaded model weights remain in the shared local model cache. Pending drafts never become retrieval evidence until an actual outcome and editor review have been recorded.

The original combined backend is retained:

```powershell
./.venv/Scripts/python.exe start.py --mode combined
```

It serves the same functionality on port 8000 with Streamlit on 8501. Stop the running setup before switching. **Never run two retrieval writers or the combined backend and split retrieval against the same state directory.** Startup rejects busy standard ports, but arbitrary manually launched writers on custom ports still require operator coordination. Local file storage is single-writer; this prototype does not claim horizontal scalability.

## Manual startup

Use three terminals in the same repository/environment. Stop the launcher first.

```powershell
./.venv/Scripts/python.exe -m uvicorn retrieval_api:app --host 127.0.0.1 --port 8001
```

```powershell
# Required mode: supply the retrieval application agent key in this shell.
$env:RETRIEVAL_URL = 'http://127.0.0.1:8001'
# $env:RETRIEVAL_API_KEY = 'your-application-agent-key'
./.venv/Scripts/python.exe -m uvicorn resolution_api:app --host 127.0.0.1 --port 8002
```

```powershell
$env:TELEASSIST_API_URL = 'http://127.0.0.1:8002'
$env:TELEASSIST_EDITOR_URL = 'http://127.0.0.1:8001'
./.venv/Scripts/python.exe -m streamlit run dashboard.py
```

The launcher accepts `--retrieval-port`, `--resolution-port`, `--dashboard-port` and `--combined-port` for isolated checks. It sets the corresponding child-process URLs automatically.

## Verification and production limits

`python -m scripts.smoke.smoke_split` starts real HTTP services on unused ports with real cached MiniLM, disables provider calls and uses temporary case/evidence storage. It verifies hybrid search, exact citation versions, no-key fallback, save/outcome/review/publication, future search in all three modes, retirement with historical citation access, and retrieval-outage fallback. Logs stay in ignored runtime storage. It stops only its owned process trees. Run `scripts/smoke/smoke_services.py` first if weights are missing.

The regression suite covers combined and split case workflows, access roles, version conflicts, topic forwarding, upstream failures, busy ports and owned-process shutdown. Integration checks verify case publication, future retrieval, restart recovery and historical citations using isolated synthetic records. These functional checks do not establish independent resolution quality. The README reports the current test count.

Production deployment still requires HTTPS, external identity/service credentials, coordinated provider quotas, shared versioned storage, durable jobs, backups and measured capacity. Docker is optional packaging; the executable service boundary is already HTTP between independent processes.
