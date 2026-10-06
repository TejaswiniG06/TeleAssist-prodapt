# Trust-aware resolution services

## Evidence ingestion and provenance

All 257 filtered public tickets are indexed as `unverified_ticket` records with `evidence_tier: unverified`, creator attribution, CC-BY-NC-4.0 licence, original row references and source labels. Their replies are suggestions with unknown outcomes. The system does not relabel them as confirmed telecom fixes. The dataset card advertises a synthetic-ticket generator but does not, by itself, establish whether every downloaded complaint was authored synthetically or came from a customer; origin is therefore marked `public_origin_unverified`. Do not describe these as verified real customer language.

Synthetic KB articles use the `kb` tier; synthetic successfully resolved history uses `resolved`. Synthetic cases whose explicit outcome is `not_resolved` use `unresolved` and cannot supply successful fixes. Tiers describe suitability for this demo, not provider approval. Even the KB is illustrative synthetic guidance.

The retrieval API combines 28 KB articles, the original two history records, 200 generated histories (160 resolved/40 not_resolved) and the 257 public records: 487 active records. Search remains capable of showing all tiers. `/resolve` retrieves separate hybrid candidate pools by record type so a large public tier cannot crowd out articles/history. Its context reserves three KB and three resolved-history slots, plus one unverified and one unresolved source when available; unused slots are filled from relevant remaining evidence. It requires a semantic relevance score of at least 0.32 before preferring KB, resolved history, then unverified suggestions. This threshold remains a development setting requiring evaluation.

## Corpus generation

Run `python -m scripts.data.generate_corpus` using a locally configured free-plan key. It requests eight batches of 25 tickets (200 total: 160 resolved and 40 not_resolved) and one article batch to reach 28 KB articles. Each ticket contains complaint, product, observations, attempted actions, conditional resolution steps, explicit `resolved`/`not_resolved` outcome and outcome evidence. Batch prompts target 20 resolved and five unresolved records. Resumable intermediate files live in ignored `runtime/corpus_batches`.

Pydantic validates every batch; exact duplicates and PII-like generated text are rejected. Partial batches are not silently published. Final output records the provider/model, counts and a checksum. Schema validation cannot prove technical correctness or diversity; generated guidance needs review before provider use. A large corpus is only useful if retrieval quality and answer grounding are evaluated.

## Masking and classification

`teleassist/common/privacy.py` masks email, phone-like sequences, IPv4 addresses, labelled names/addresses, account IDs and common secrets before retrieval or hosted generation. It does not log raw input or retain a reverse mapping. Pattern masking is incomplete for names, postal addresses and unusual identifier formats; this is a prototype privacy control, not comprehensive anonymization.

`teleassist/resolution/pipeline.py` classifies product, category, severity, sentiment and attempted actions through structured LLM output. Categories remain extensible and unknown labels are allowed. Attempted actions must cite an exact passage in the current complaint/observations. Recognized attempted actions are excluded from suggestions even when their outcome is unknown; common router restart aliases normalize to one action ID. Unrecognized actions and ambiguous outcomes still require clarification. With no key, a limited local classifier supports a clearly marked fallback.

## Cited draft and validation

`POST /resolve` accepts `complaint`, optional `observations`, and optional `exclude_source_ids` for evaluation. It returns classification, masked complaint, steps, questions, citations, retrieved source summaries, generation status and citation-check status.

The model selects steps from evidence options instead of inventing instructions freely. The server verifies source ID, version, action ID, an exact support quote, and a customer-text passage for applicability. Returned instructions come from the selected source. An unverified step begins “A similar past ticket suggested…” and explicitly discloses that its applicability and outcome are unverified. Nonresolved tickets cannot supply resolution steps. Suspicious source instructions, duplicate actions, fabricated citations or unsupported quotes produce a clarification fallback.

These checks establish source membership and textual support, not full semantic entailment or that all conditions hold. The LLM still judges applicability; the result is an agent-review draft. Unknown conditions should produce clarification. The prototype does not claim a diagnosis, guarantee a fix, or automatically perform an action.

## Free provider and quota handling

Use the Gemini Developer API free tier through a key created in Google AI Studio. A Gemini app/Google AI Pro subscription is separate from API billing. Store the key only in ignored `.env`; `.env.example` contains safe configuration placeholders. The client requires an explicit free-plan configuration, limits model choices to a checked free-tier allowlist, and never upgrades billing or switches automatically to a paid service. The checkpoint uses Gemini 3.5 Flash-Lite. Model availability and free quotas depend on the provider and account; check the official pricing and rate-limit pages before enabling generation. Regular free-tier text generation is used, not Google Search grounding or separately priced Batch API jobs.

The client spaces requests, honors bounded Retry-After backoff and retries quota/temporary server errors at most twice. Persistent quota or provider errors yield a clarification fallback. These are regular API calls asking for 25 records each, not a provider's separately priced Batch API. Pacing is process-local and must be replaced with a shared limiter for multiple workers. Actual limits depend on the account; batching also has to respect token quotas.

Official references: [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing), [API rate limits](https://ai.google.dev/gemini-api/docs/rate-limits), [Groq rate limits](https://console.groq.com/docs/rate-limits).

## Current-state clarification

Current-state clarification checks whether a reported change may still interrupt service. Removing a SIM does not establish that it was reinserted; unplugging a cable does not establish reconnection. A small local rule module covers common service prerequisites, and the existing classification call can propose questions for other missing or contradictory states using exact customer quotes. Unknown states return questions before retrieval or step selection. Both yes and no answers establish the current state and allow the request to continue; no does not mean the prerequisite has been restored. Answered state questions are filtered from later classification and drafting, including common paraphrases. A supported next step is selected when available; otherwise the system escalates rather than repeatedly asking the same question. No extra provider call is added.

SIM reseating aliases also cover opaque source action IDs, so recognized completed reseating is excluded from future options. Historical step selection is instructed to require the stated circumstances, rather than infer an OS update or warning from a shared symptom. Exact quote checks are still mechanical; these changes do not establish complete semantic applicability or coverage of every wording. The frozen earlier evaluation results remain measurements of the earlier classifier.

## Public-query evaluation

`python -m teleassist.retrieval.evidence` reserves 25 public complaint queries with stable hash-based selection. `python -m scripts.evaluation.evaluate_public` compares keyword, semantic and hybrid results while excluding the original public record from each query. All public records remain searchable for normal requests. Use `--resolve` only when intentionally evaluating generation and its API quota.

The public query file retains source attribution. It is query-only: manual relevance and expected-behaviour annotation is still needed. Self-match exclusion is not a substitute for near-duplicate audit. These cases are not a finished benchmark, and no recall/accuracy claims should be made until labels and split isolation are reviewed. Use public out-of-taxonomy records later for emerging-topic detection.

## Validation and limits

The current regression suite covers masking, source trust, attempted-action aliases, state-question continuation, citation membership, source-instruction injection and provider failure. Run `python -m unittest discover -s tests -q` from the repository root. The README reports the current test count and frozen evaluation results.

Software checks do not establish answer quality. A source-backed step can still have an unconfirmed applicability condition, historical step wording can read as a completed action, and generic fallbacks may ask for information already supplied. Independent applicability review and broader conversational tests remain necessary.

Application-key roles, background ingestion, case publication, reviewed topic proposals and process monitoring are implemented; see the corresponding technical guides. Production still requires per-user identity, shared durable storage/queues, coordinated quotas and comprehensive privacy controls. Pattern masking does not recognize every personal identifier; use synthetic or appropriately anonymized demonstration inputs.
