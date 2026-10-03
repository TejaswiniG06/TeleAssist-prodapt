# Retrieval services walkthrough

## Dataset preparation

`prepare_tickets.py` reads the downloaded public CSV and writes an auditable candidate pool and aggregate report. It filters English network-related complaints, retains original labels and attribution, and marks every answer as unverified. `evidence.py` now imports all 257 into the searchable unverified tier. It does not turn a support reply into a successful fix. Run `python prepare_tickets.py scratch/tobi-tickets.csv` to reproduce the audit. The [trust and resolution walkthrough](03-trust-and-resolution.md) supersedes the earlier grounding exclusion.

`expand_evidence.py` adds four manually authored synthetic articles without replacing the original five sources. It also records product/category labels and unknown severity/sentiment. Run it again safely: existing IDs are preserved. These are illustrative diagnostic records, not provider-approved instructions or full telecom coverage.

## Keyword retrieval

The existing `retrieval.py` BM25 implementation is preserved. It ranks exact term matches and excludes retired records. IDs and provenance are excluded from searchable text. All four original checks remain relevant.

## Semantic retrieval

`semantic.py` uses the free local `sentence-transformers/all-MiniLM-L6-v2` model on CPU. The first use downloads model weights; later searches run locally without an API key or per-request fees. Sentence embeddings express text meaning as vectors. Cosine similarity ranks complaints and evidence even when their words differ.

The index excludes retired sources and accepts a minimum cosine score. The default 0.30 is a development setting, not a calibrated confidence or guarantee of relevance. Model identity plus a hash of searchable text keys the embedding cache. Unchanged texts reuse embeddings, changed texts are recomputed, and removed records disappear from the current index/cache. This is incremental reuse, not background ingestion or a complete resource monitor.

## Hybrid retrieval

`HybridIndex` combines BM25 and semantic candidate ranks with reciprocal-rank fusion: each appearance contributes `1 / (60 + rank)`. This avoids treating incomparable BM25 and cosine scores as the same scale. Returned component ranks/scores make the result inspectable. Fusion scores measure ranking, not confidence. The prototype uses a 20-result pool from each method; larger corpora need evaluated pool sizes and a scalable index.

## FastAPI evidence service

Run `python -m uvicorn api:app --host 127.0.0.1 --port 8000` inside the virtual environment. Interactive endpoint documentation is at http://127.0.0.1:8000/docs.

- `POST /search`: query, mode (`keyword`, `semantic`, `hybrid`), limit, minimum semantic score, optional product and record-type filters. Filters apply before ranking. Responses include source records, provenance, versions and clickable relative source URLs.
- `GET /sources/{id}`: returns an active evidence record; missing/retired IDs return 404.
- `GET /health`: reports active source count and semantic readiness. Embeddings load lazily on first semantic/hybrid search, so keyword search needs no model download. Embedding failure yields 503 for semantic/hybrid; keyword remains usable and health reports degradation.

The API validates blank/oversized queries, result limits, modes and thresholds. `/resolve` adds masking, classification, attempted-action awareness and checked source-based generation. Agent/editor access and validated background updates are now implemented; see docs/06-access-and-updates.md. `/search` itself returns evidence without generating an answer.

Official references: https://www.sbert.net/docs/sentence_transformer/usage/semantic_textual_similarity.html and https://fastapi.tiangolo.com/tutorial/first-steps/.

## Verification

Verified on 2026-10-03 with Python 3.13: all nine unit tests pass, including the four original BM25 tests. Unit tests cover semantic ranking with a deterministic encoder, retired-source exclusion, hybrid component ranks, incremental cache invalidation, API validation, metadata filters, source links, and embedding-service failure isolation.

`python smoke_services.py` also passed using the real downloaded MiniLM model through FastAPI TestClient. For “My internet crawls and videos keep stalling”, semantic returned TICKET-002 then KB-002; hybrid ranked KB-002 first. The mobile-filtered query retrieved KB-005, source lookup worked, and health reported nine active sources with semantic readiness. The report is saved in ignored `runtime/smoke-report.json`. This is an integration smoke check, not a full quality benchmark or live network-server test. Existing evaluation seeds remain development data, not a held-out benchmark.

`requirements-lock.txt` records installed dependency versions. The current Starlette test client emits an httpx deprecation warning; requests and assertions passed. This section records the original retrieval milestone; current free-provider generation and evidence counts are described in README.md and docs/03-trust-and-resolution.md.
