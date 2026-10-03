# Single process and separated service modes

Keep the default reviewer setup: `uvicorn api:app --host 127.0.0.1 --port 8000`. It runs the same modules in one process and serves the interface.

To demonstrate separate services, start two terminals from the project environment:

```powershell
python -m uvicorn retrieval_api:app --host 127.0.0.1 --port 8001
python -m uvicorn resolution_api:app --host 127.0.0.1 --port 8002
```

Open http://127.0.0.1:8002/. The resolution service owns masking/classification, LLM calls, grounding checks and the interface. It forwards evidence/search/taxonomy requests over HTTP to the retrieval service. The retrieval service owns the catalog, embeddings, updates, topic review and source history; it has no `/resolve` route and requires no provider key. These are separately executable service processes, not just different endpoint names.

`RETRIEVAL_URL` selects the upstream service. With required authentication, set `RETRIEVAL_API_KEY` to an application agent key accepted by retrieval; never supply the provider key there. User access is checked by resolution, and its service credential is checked by retrieval. Editor evidence/topic actions go directly to retrieval's editor APIs. Each service has its own liveness/readiness and role-protected metrics. Resolution health depends on upstream health but does not claim a configured LLM is reachable.

Resolution fetches one index version and requests each evidence pool with that expected version. An update between pools produces a safe retry/clarification rather than mixed-version grounding. Versioned citations remain inspectable after publication. Upstream connection, access or availability errors produce a controlled fallback. External service URLs are configuration, never customer-input destinations. Use HTTPS, identity/service credentials and coordinated quotas before public deployment.

`python smoke_split.py` starts two temporary local processes on unused ports, warms retrieval, checks real HTTP hybrid search and versioned evidence, checks key-free drafting, then stops its own retrieval child and verifies outage fallback. It uses already downloaded model weights with Hugging Face offline mode, disables provider calls and terminates only its own child processes. Run smoke_services.py first if the weights are not cached. Logs stay in ignored runtime storage. Unit tests additionally cover separate user/service keys and version conflict responses.

The gateway's retrieval timeout is 60 seconds. Cold model initialization can exceed an interactive budget: an initial HTTP smoke attempt timed out during its first hybrid call. Warm retrieval before opening semantic-dependent traffic and check `/ready?require_semantic=true`; keyword remains available while the model has not loaded. Cached/offline smoke verification checks service behaviour without depending on hub metadata availability.

Do not run two retrieval writers or the all-in-one server and split retrieval against the same runtime state simultaneously. The file catalog is single-writer; multi-worker retrieval requires shared versioned storage and coordination. Separating processes demonstrates the boundary, not horizontal scale. Local single-process mode remains the simplest reviewer path.
