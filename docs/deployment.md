# Deployment and configuration

The recommended reviewer setup runs **two separate FastAPI services** and a Streamlit dashboard. No Docker installation is needed. Each backend has its own process, port, lifecycle and metrics; the resolution service calls retrieval over HTTP.

## Install and configure

Follow the [README quick start](../README.md#run-locally): create the Python 3.13 environment, install `requirements-lock.txt` and copy `.env.example` to `.env`. Configure a confirmed-free API project for live classification/drafting. Without a provider key, search and limited classification fallback remain available. The initial semantic-model download requires internet.

The clone includes 230 synthetic records. Run `python -m scripts.data.download_public` for the optional 257 public records used in the frozen evaluations. Runtime state and keys are ignored by Git.

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

## Application access

An agent can search and prepare drafts; an editor can also change evidence. Keys map to those two roles. They are application credentials, separate from the Gemini provider key, and should be kept private. The example editor key `editor` is intentionally provided for the local demo; replace it before shared hosting.

`AUTH_MODE=local` keeps the localhost reviewer demo usable without credentials. Anonymous users have agent permissions only. Editor access always needs `TELEASSIST_EDITOR_KEY`. In `required` mode, both agent and editor keys must be present and different or configuration fails. An absent/invalid request key returns 401; a valid agent key used on editor routes returns 403. `/admin/access` verifies editor access.

Supply `X-API-Key` in API requests, use the Swagger Authorize control, or enter the agent key in the browser access field. The dashboard holds the application key in its current session. Raw source links opened in a new tab cannot carry this custom header in required mode; “View evidence” fetches with the header. Switch role clears the dashboard access session.

This is role-based access for a local prototype, not full user identity management. Public hosting requires required mode behind HTTPS and per-user identity/OIDC, rotation/revocation and shared quotas. Public health and the interface shell contain no evidence text or credentials. Bind local mode to 127.0.0.1.


## Provider configuration and quotas


Use the Gemini Developer API free tier through a key created in Google AI Studio. A Gemini app/Google AI Pro subscription is separate from API billing. Store the key only in ignored `.env`; `.env.example` contains safe configuration placeholders. The client requires an explicit free-plan configuration, limits model choices to a checked free-tier allowlist, and never upgrades billing or switches automatically to a paid service. The recorded evaluations use Gemini 3.5 Flash-Lite. Model availability and free quotas depend on the provider and account; check the official pricing and rate-limit pages before enabling generation. Regular free-tier text generation is used, not Google Search grounding or separately priced Batch API jobs.

The client spaces requests, honors bounded Retry-After backoff and retries quota/temporary server errors at most twice. Persistent quota or provider errors yield a clarification fallback. These are regular API calls asking for 25 records each, not a provider's separately priced Batch API. Pacing is process-local and must be replaced with a shared limiter for multiple workers. Actual limits depend on the account; batching also has to respect token quotas.

Official references: [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing), [API rate limits](https://ai.google.dev/gemini-api/docs/rate-limits), [Groq rate limits](https://console.groq.com/docs/rate-limits).

## Common startup checks

- If a port is occupied, stop the previous application or use the launcher's port options.
- If semantic warmup times out, pre-download the model or use `--skip-warmup` for keyword-only startup.
- If editor access fails, check `TELEASSIST_EDITOR_KEY`; the provider key does not grant application permissions.
- If generation falls back, inspect the returned reason and backend logs for configuration, quota, provider or grounding failures.
- If an update returns 409, reload the latest source/case/index version before resubmitting.

Use synthetic or appropriately anonymized demonstration inputs. Pattern masking does not cover every personal identifier.
