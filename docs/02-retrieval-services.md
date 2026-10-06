# Retrieval services walkthrough

## Dataset preparation

`scripts/data/prepare_tickets.py` reads the downloaded public CSV and writes an auditable candidate pool and aggregate report. It filters English network-related complaints, retains original labels and attribution, and marks every answer as unverified. `teleassist/retrieval/evidence.py` now imports all 257 into the searchable unverified tier. It does not turn a support reply into a successful fix. Run `python -m scripts.data.prepare_tickets scratch/tobi-tickets.csv` to reproduce the audit. See [trust and resolution](03-trust-and-resolution.md) for use of unverified replies.

`scripts/data/expand_evidence.py` adds four synthetic starter articles without replacing the original five sources. It also records product/category labels and unknown severity/sentiment. Run it again safely: existing IDs are preserved. These are illustrative diagnostic records, not provider-approved instructions or full telecom coverage.

## Keyword retrieval

The existing `teleassist/retrieval/keyword.py` BM25 implementation is preserved. It ranks exact term matches and excludes retired records. IDs and provenance are excluded from searchable text. All four original checks remain relevant.

## Semantic retrieval

`teleassist/retrieval/semantic.py` uses the free local `sentence-transformers/all-MiniLM-L6-v2` model on CPU. The first use downloads model weights; later searches run locally without an API key or per-request fees. Sentence embeddings express text meaning as vectors. Cosine similarity ranks complaints and evidence even when their words differ.

The index excludes retired sources and accepts a minimum cosine score. The default 0.30 is a development setting, not a calibrated confidence or guarantee of relevance. Model identity plus a hash of searchable text keys the embedding cache. Unchanged texts reuse embeddings, changed texts are recomputed, and removed records disappear from the current index/cache. This is incremental reuse, not background ingestion or a complete resource monitor.

## Hybrid retrieval

`HybridIndex` combines BM25 and semantic candidate ranks with reciprocal-rank fusion: each appearance contributes `1 / (60 + rank)`. This avoids treating incomparable BM25 and cosine scores as the same scale. Returned component ranks/scores make the result inspectable. Fusion scores measure ranking, not confidence. The prototype uses a 20-result pool from each method; larger corpora need evaluated pool sizes and a scalable index.

## FastAPI evidence service

The recommended launcher starts the retrieval service on port 8001. For manual startup, run `python -m uvicorn retrieval_api:app --host 127.0.0.1 --port 8001` inside the virtual environment. Interactive endpoint documentation is at http://127.0.0.1:8001/docs. The combined API on port 8000 remains a compatibility option.

- `POST /search`: query, mode (`keyword`, `semantic`, `hybrid`), limit, minimum semantic score, optional product and record-type filters. Filters apply before ranking. Responses include source records, provenance, versions and clickable relative source URLs.
- `GET /sources/{id}`: returns an active evidence record; missing/retired IDs return 404.
- `GET /health`: reports active source count and semantic readiness. Embeddings load lazily on first semantic/hybrid search, so keyword search needs no model download. Embedding failure yields 503 for semantic/hybrid; keyword remains usable and health reports degradation.

The API validates blank/oversized queries, result limits, modes and thresholds. `/resolve` adds masking, classification, attempted-action awareness and checked source-based generation. Agent/editor access and validated background updates are now implemented; see docs/06-access-and-updates.md. `/search` itself returns evidence without generating an answer.

Official references: https://www.sbert.net/docs/sentence_transformer/usage/semantic_textual_similarity.html and https://fastapi.tiangolo.com/tutorial/first-steps/.

## Verification

The regression suite covers BM25, semantic ranking with a deterministic encoder, retired-source exclusion, hybrid component scores, cache invalidation, API validation, metadata filters and embedding failure. Filters apply before ranking; unchanged source vectors remain cached. Filtering after taking top results could discard eligible sources when excluded records occupy those positions.

`python -m scripts.smoke.smoke_services` checks real local MiniLM and API integration. `python -m scripts.smoke.smoke_split` checks independent HTTP services with isolated storage. These are functional checks, not a relevance benchmark. See the [evaluation guide](10-evaluation.md) for frozen query sets and limitations, and the README for the current test count and corpus setup.
