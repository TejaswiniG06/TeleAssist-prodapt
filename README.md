# Broadband Support Assistant

An educational prototype for Prodapt use case 2: evidence-backed telecom troubleshooting that accounts for attempted actions. Privacy, grounding, access roles, versioned updates and process monitoring are implemented. This is a working prototype with production-oriented design, not a production-ready deployment.

## Reviewer quick start (Windows PowerShell)

Run from the cloned repository folder. No author credentials or API key are required for tests, the interface, or retrieval.

```powershell
git clone https://github.com/TejaswiniG06/TeleAssist-prodapt.git
cd TeleAssist-prodapt
py -3.13 -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements-lock.txt
./.venv/Scripts/python.exe -m unittest discover -s tests -v
./.venv/Scripts/python.exe -m uvicorn api:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/. Try “slow broadband speed” with keyword search, then inspect the source evidence. Semantic/hybrid search downloads a local embedding model on first use and requires internet for that initial download. The clone contains 230 synthetic records; optional public-data setup is described below.

Without an LLM key, “Prepare draft” returns a clarification fallback, not an LLM-generated resolution. The behavioural tests use local/fake dependencies and do not need provider credentials. `smoke_resolution.py` tests live generation and requires optional configuration.

To enable live drafting, copy `.env.example` to `.env` only if `.env` does not already exist. Supply **your own** `GEMINI_API_KEY` locally and set `LLM_FREE_PLAN_CONFIRMED=true` only after confirming your provider project uses the intended free plan. Never use or request the author's key. The flag is a configuration check; it cannot inspect billing settings or guarantee provider availability. Keep the other example settings initially; model access and quotas can vary. Restart the server after changing configuration.

The author's key was used only for local live checks and corpus generation. Generated synthetic records are committed, so reviewers do not need to regenerate them or access that key. `.env`, downloaded model weights, raw public data and runtime files are excluded from Git. The interface does not receive the provider key.

Locked dependencies were installed in a fresh Python 3.13 virtual environment and passed `pip check`. The regression suite and browser interface have also been checked; see [evaluation methodology](docs/10-evaluation.md) for independent label review and production-deployment gaps.

## Current progress

The corpus now has 487 searchable records: 28 synthetic KB articles, 162 resolved histories (160 generated plus the original two), 40 generated not-resolved histories, and 257 public tickets in an unverified tier with attribution. The original nine records are preserved. Batched corpus generation is handled by `generate_corpus.py`, with explicit outcomes and duplicate checks.

BM25, local semantic retrieval, hybrid rank fusion and FastAPI evidence/resolve endpoints are implemented. `/resolve` adds masking, classification, attempted-action awareness, trust-aware source selection, citation checks and clarification fallback. Optional Gemini 3.5 Flash-Lite drafting uses a locally supplied confirmed-free key; no key is distributed. Agent/editor access, versioned background evidence updates, reviewed emerging-topic proposals, monitoring and optional separated HTTP services are implemented. Progress and limitations stay tracked in docs/scope.md.

Setup: `py -3.13 -m venv .venv`, then `.venv/Scripts/python.exe -m pip install -r requirements-lock.txt` for the verified versions (or `requirements.txt` for compatible ranges). Activate the environment with `.venv/Scripts/Activate.ps1` before the commands below. Semantic retrieval downloads a free local model into workspace runtime storage on first use; no paid API or API key is used.

Verification commands: `python -m unittest discover -s tests -v`, `python smoke_services.py`, `python evaluate_public.py`, and `python smoke_resolution.py` (the last uses the configured free LLM provider).

Latest checks: 50 behavioural tests pass; real-model ingestion and two-process HTTP checks pass; browser checks cover search, evidence display, clarification/error rendering and mobile layout. A frozen 24-query partial-reference pilot compares all retrieval modes; 25 public queries exclude self/near-duplicate matches. Live generation checks pass. A six-case author-labelled classification pilot matched product/category/sentiment in 6/6 each and severity in 2/6; independent relevance/applicability review and an approved urgency policy remain necessary.

A fresh clone includes 230 synthetic evidence records. Run `python download_public.py` to download the pinned, checksum-verified public CSV and recreate 257 optional candidates in ignored `scratch/prepared/tobi_candidates.json`. The source is attributed to Tobi-Bueck / Softoft under its declared CC-BY-NC-4.0 licence; see docs/dataset-audit.md. The API runs without those optional public records, and missing provider configuration produces clarification rather than an unchecked resolution.

Start the API: `python -m uvicorn api:app --host 127.0.0.1 --port 8000`. Open http://127.0.0.1:8000/docs. See [service walkthrough](docs/02-retrieval-services.md) for explanations and limitations.

Open http://127.0.0.1:8000/ for the plain browser interface: enter a complaint, find evidence or prepare a cited draft, then inspect its sources. See [the interface explanation](docs/04-interface.md).

See [trust and resolution services](docs/03-trust-and-resolution.md) for the pipeline, evidence tiers, corpus generation, free-plan setup and evaluation limitations. Keep the API key in ignored `.env`; never paste it into source or commit it. Free-plan configuration is required, and no paid-provider fallback is performed.

Run the baseline with Python: `python retrieval.py "slow speed buffering"`.
Run checks: `python -m unittest discover -s tests -v`.

See docs/dataset-audit.md for findings from the suggested public ticket dataset, and docs/scope.md for the full agreed feature checklist.

The KB and generated history are illustrative synthetic data, not approved provider guidance. Public ticket origin and outcomes are unverified. Public texts are pattern-masked at ingestion, with attribution and their noncommercial licence retained; pattern masking is not comprehensive anonymization.

## Implemented backend services

| Service | Responsibility | Explanation |
| --- | --- | --- |
| Access | Agent/editor application keys; optional key-free localhost agent mode | [Access and updates](docs/06-access-and-updates.md) |
| Evidence catalog | Validate batches, check versions, build in background, atomically publish and preserve citation history | [Access and updates](docs/06-access-and-updates.md) |
| Retrieval and resolution | BM25/local vectors/hybrid plus checked drafts or clarification | [Grounding](docs/03-trust-and-resolution.md) |
| Emerging topics | Group weak matches; require editor taxonomy review; never auto-create fixes | [Topic review](docs/08-emerging-topics.md) |
| Monitoring | Liveness/readiness, bounded latency/error/fallback counters and process resources | [Monitoring](docs/07-monitoring.md) |
| Split deployment | Run retrieval and resolution as two HTTP services, or keep the simple single-process demo | [Service deployment](docs/09-service-deployment.md) |
| Evaluation | Frozen partial-reference retrieval pilot, public-query leakage exclusions, classification diagnostics and failure checks | [Evaluation](docs/10-evaluation.md) |

Additional checks: `python smoke_updates.py`, `python smoke_split.py` (cached local model required), `python benchmark_local.py`, `python evaluate_benchmark.py`, and `python evaluate_classification.py` (optional live provider). Runtime reports and operational updates remain ignored. See the evaluation walkthrough for measured results and limits; no 100% real-world accuracy or production-capacity claim is made.

## Remaining project phases

The supplied scoring rubric, required deliverables and remaining evidence gaps are mapped in [evaluation methodology](docs/10-evaluation.md). See [architecture](docs/architecture.md) for current and proposed diagrams, its production deployment section for scaling limits, and [design decisions](docs/design-decisions.md) for the choices and tradeoffs. This is a working prototype with explicitly tracked production and evaluation gaps.

1. Improve the support-agent and editor interface.
2. Finish repository/file cleanup after the prototype is complete.
3. Walk through the architecture, workflow, design tradeoffs and code; rehearse the interview.
4. Independently review benchmark relevance/applicability and urgency labels before final scoring or operational use.

See [Lesson 1](docs/01-data-foundation.md) for the first walkthrough.

See [code defence](docs/05-code-defence.md) for each module's responsibility, design tradeoffs and interview questions.

See [access and update controls](docs/06-access-and-updates.md) for local and authenticated modes. Use separate application agent/editor keys; these are not the LLM provider key.
