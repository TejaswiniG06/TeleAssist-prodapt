# Project structure and reading order

The cleanup groups existing code by responsibility. Retrieval/drafting algorithms, API request/response contracts, evidence data and local case storage are preserved. This is package organisation and view extraction, not a change to the problem scope.

```text
TeleAssist-prodapt/
  start.py                   Local process launcher
  dashboard.py               Small Streamlit entry point
  api.py                     Combined compatibility entry point
  retrieval_api.py           Retrieval service entry point
  resolution_api.py          Resolution service entry point
  teleassist/
    services/                HTTP routes, shared schemas and case routes
    retrieval/               Keyword, semantic/hybrid, query building and evidence loading
    resolution/              Classification/drafting/checks and free-provider client
    ingestion/               Validated catalog updates and index publication
    cases/                   Transactional SQLite case store
    common/                  Access, masking, metrics and stable project paths
    topics.py                Topic grouping and reviewed taxonomy
  frontend/
    app.py                   Role selection and navigation
    client.py                HTTP boundary
    components.py            Safe shared rendering, examples and source navigation
    styles.css               Existing theme/animations
    views/                   Agent, cases, evidence, topics and health
  scripts/
    data/                    Download/filter/generate/repair tools
    evaluation/              Retrieval, classification, language and load measurements
    smoke/                   Real-model and service integration checks
  tests/                     Behaviour and failure checks
  data/                      Evidence, frozen queries and evaluation summaries
  docs/                      Scope, design, setup and limitations
  web/                       Preserved original lightweight interface
  runtime/                   Ignored persistent SQLite, caches and logs
  scratch/                   Ignored development diagnostics; not submission code
```

## Reading the complaint path

1. Start at `frontend/views/agent.py`: form, Prepare draft, cited response and explicit saving.
2. `frontend/client.py` sends HTTP; it contains no retrieval or model decisions.
3. `teleassist/services/resolution.py` validates requests and calls the resolver.
4. `teleassist/resolution/pipeline.py` masks/classifies, excludes attempted actions, retrieves evidence and validates a response.
5. `teleassist/retrieval/` implements BM25, local embeddings, hybrid rank fusion and classification-aware query construction.
6. `teleassist/ingestion/catalog.py` manages versioned evidence; `teleassist/cases/store.py` keeps pending cases and actual outcomes before reviewed publication.

HTTP schemas live in `teleassist/services/schemas.py`; resolution does not import the combined application just to obtain its input models. The combined/retrieval factory shares the existing catalog and case implementation; separate-service mode is a process/HTTP boundary, not duplicated algorithms.

## Running and reusing tools

Existing commands remain valid:

```powershell
./.venv/Scripts/python.exe start.py
./.venv/Scripts/python.exe start.py --mode combined
./.venv/Scripts/python.exe -m streamlit run dashboard.py
```

The root API files are small deployment entry points; `uvicorn retrieval_api:app`, `uvicorn resolution_api:app` and `uvicorn api:app` remain valid. The launcher still configures the real dashboard addresses and supports both modes.

Run moved tools using standard Python module syntax from the repository root:

```powershell
./.venv/Scripts/python.exe -m scripts.smoke.smoke_split
./.venv/Scripts/python.exe -m scripts.data.prepare_tickets --help
./.venv/Scripts/python.exe -m scripts.evaluation.evaluate_query_enrichment
```

`teleassist/common/paths.py` anchors data, model-cache and web assets to the repository root. SQLite keeps the same `runtime/cases.sqlite3` name; evidence/topic files and `TELEASSIST_STATE_DIR` work as before. Moving a Python file does not create a new database or regenerate datasets. Frozen classification replay normalizes only the three moved imports in its V1 source fingerprint; changed classifier logic still invalidates the cache. No evaluation labels or scores were edited to make the cleanup pass.

The old duplicate tier labels and unused citation-rendering/editor-composition helpers were removed. Shared safe source rendering lives in one component module. The two requirement files have different purposes (compatible ranges versus reproducible lock) and remain. Existing data-generation and repair tools remain available for provenance/reproducibility.

No new runtime dependencies, inheritance layers or plugin mechanisms were added. The cleanup checkpoint passed 87 tests; later UI changes increased the current suite to 93 tests; real HTTP and browser checks verify integration separately.

Cleanup verification: all 87 tests passed; real HTTP split checks covered retrieval, case publication, future search, retirement/history and outage fallback. A fresh isolated browser audit with real MiniLM passed editor login, all editor screens, topic approval, case publication, evidence addition/retirement and narrow-screen layout. The live agent/editor browser checks also passed. All 11 committed data files are byte-for-byte unchanged, and the 13 extracted screen functions retain their original syntax trees. No provider calls were needed for this refactor.
