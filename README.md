# Broadband Support Assistant

An educational prototype for Prodapt use case 2: evidence-backed broadband troubleshooting that accounts for attempted actions, with privacy controls and resource monitoring.

## Current progress

The corpus now has 487 searchable records: 28 synthetic KB articles, 162 resolved histories (160 generated plus the original two), 40 generated not-resolved histories, and 257 public tickets in an unverified tier with attribution. The original nine records are preserved. Batched corpus generation is handled by `generate_corpus.py`, with explicit outcomes and duplicate checks.

BM25, local semantic retrieval, hybrid rank fusion and FastAPI evidence/resolve endpoints are implemented. `/resolve` adds masking, classification, attempted-action awareness, trust-aware source selection, citation checks and clarification fallback. Gemini 3.5 Flash-Lite is configured through the local free-tier API key. Authentication and the remaining agreed capabilities stay tracked in docs/scope.md.

Setup: `py -3.13 -m venv .venv`, then `.venv/Scripts/python.exe -m pip install -r requirements-lock.txt` for the verified versions (or `requirements.txt` for compatible ranges). Activate the environment with `.venv/Scripts/Activate.ps1` before the commands below. Semantic retrieval downloads a free local model into workspace runtime storage on first use; no paid API or API key is used.

Verification commands: `python -m unittest discover -s tests -v`, `python smoke_services.py`, `python evaluate_public.py`, and `python smoke_resolution.py` (the last uses the configured free LLM provider).

Latest checks: 27 unit tests pass; 25 public-query retrieval comparisons exclude self matches; live Gemini resolution checks pass for historical grounding, clarification and KB guidance. Manual relevance labels and a final quality benchmark are still pending.

A fresh clone includes 230 synthetic evidence records. The additional 257 public candidates are loaded from ignored `scratch/prepared/tobi_candidates.json`; prepare them with `python prepare_tickets.py scratch/tobi-tickets.csv` after obtaining the audited source CSV described in docs/dataset-audit.md. A pinned download workflow is still pending. The API runs without those optional public records, and missing provider configuration produces clarification rather than an unchecked resolution.

Start the API: `python -m uvicorn api:app --host 127.0.0.1 --port 8000`. Open http://127.0.0.1:8000/docs. See [service walkthrough](docs/02-retrieval-services.md) for explanations and limitations.

Open http://127.0.0.1:8000/ for the plain browser interface: enter a complaint, find evidence or prepare a cited draft, then inspect its sources. See [the interface explanation](docs/04-interface.md).

See [trust and resolution services](docs/03-trust-and-resolution.md) for the pipeline, evidence tiers, corpus generation, free-plan setup and evaluation limitations. Keep the API key in ignored `.env`; never paste it into source or commit it. Free-plan configuration is required, and no paid-provider fallback is performed.

Run the baseline with Python: `python retrieval.py "slow speed buffering"`.
Run checks: `python -m unittest discover -s tests -v`.

See docs/dataset-audit.md for findings from the suggested public ticket dataset, and docs/scope.md for the full agreed feature checklist.

The KB and generated history are illustrative synthetic data, not approved provider guidance. Public ticket origin and outcomes are unverified. Public texts are pattern-masked at ingestion, with attribution and their noncommercial licence retained; pattern masking is not comprehensive anonymization.

## Build sequence

The supplied scoring rubric, required deliverables and remaining evidence gaps are mapped in [design decisions](docs/design-decisions.md). See [architecture and design defence](docs/architecture.md) for current and proposed diagrams. This is a working prototype with explicitly tracked production and evaluation gaps.

1. Understand and validate the data.
2. Implement keyword retrieval as a baseline.
3. Add local embeddings and hybrid retrieval.
4. Integrate one free-tier generation provider and validate responses.
5. Add the interface, controlled knowledge updates, privacy and failure handling.
6. Evaluate, document scaling decisions, and rehearse the interview.

See [Lesson 1](docs/01-data-foundation.md) for the first walkthrough.

See [code defence](docs/05-code-defence.md) for each module's responsibility, design tradeoffs and interview questions.
