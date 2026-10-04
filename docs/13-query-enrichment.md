# Classification-aware retrieval queries

Previously resolution searched only the masked complaint and observations. It now appends the existing classification's product, category, normalized symptom phrases and normalized attempted-action names. This bridges casual customer wording to standard telecom vocabulary. Sentiment, severity and churn are omitted because they do not identify technical evidence. Unknown labels and duplicate metadata phrases are omitted. The final search text is masked and bounded to 2,000 characters, with at most 600 metadata characters. No synonym dictionary is fitted to evaluation reference IDs.

retrieval_query.py is a pure string builder: it does not call a model, retrieve sources or choose a resolution. The classification schema now includes up to six short symptom phrases, extracted in the existing classification call. Resolution still makes its existing classification call and optional drafting call. There is no additional query-rewriting call.

## Comparable API modes

POST /resolve accepts query_mode="enriched" (default) or "raw". The dashboard's Resolution search query control exposes both. Raw retains the original masked-context query and the same maximum length. Single-process and separated resolution services reuse the same builder; upstream retrieval receives the already built query.

POST /search retains raw mode by default and never calls an LLM. To compare enriched retrieval directly, supply query_mode="enriched" and an existing Classification object. Enriched search without classification returns 422. Product/type filters, source exclusions, thresholds and ranking remain independent of query construction. Client-supplied metadata is a retrieval hint, not evidence or permission to bypass grounding. Evidence Explorer continues using key-free raw searches.

The original masked customer text is retained for drafting and exact applicability evidence checks. Inferred symptom phrases cannot establish that a customer condition is true. Tests force a phrase that occurs only in metadata and verify that a draft trying to cite it as customer evidence is rejected. Emerging-topic samples retain the original request text rather than appended classifier vocabulary.

## Paired evaluation

`python evaluate_query_enrichment.py --refresh-classifications` creates or resumes predictions with the configured confirmed-free provider. There is one classification per frozen input, shared by keyword/semantic/hybrid raw and enriched searches. Only the query and allowed category schema reach classification; expected product labels and reference source IDs are never supplied. A failed classification falls back to local labels, remains in the denominator and is reported.

`python evaluate_query_enrichment.py` replays the committed prediction cache without any provider key. Query fingerprints and classifier/schema hashes protect against stale inputs. The report records the query-builder hash, corpus hash, cached predictions and identical retrieval settings: 487 records, no product/type filter, 0.30 semantic threshold, limit 20 and assessment at five. The original 24-query pilot and 10-query casual/typo set stay frozen and separate. Both variants run in the same API instance. Rank settings, references and corpus are unchanged.

Snapshots in data/query_classifications_v1.json and data/query_enrichment_results_v1.json make the comparison reviewable without the author's credentials. These are cached provider predictions on development inputs, not independent human labels. Cached evaluation measures the retrieval change conditional on those predictions; live production quality still depends on classification correctness. Added context can help or distract retrieval, so regressions must be reported as well as improvements. Synthetic vocabulary overlap and incomplete reference labels remain limitations.

To reproduce the 487-record checkpoint from a fresh clone, run download_public.py first; without the optional pinned public candidates, the bundled corpus has 230 records and scores may differ. The report records the actual corpus count/hash. Code fingerprints normalize Git line endings for portable replay. Explicit refresh regenerates predictions if the classifier, taxonomy or provider/model changes; otherwise it resumes existing matching inputs.

## Recorded before/after checkpoint

34 shared Gemini 3.5 Flash-Lite classifications completed without failures. No LLM was used to rewrite queries, and cached replay makes zero provider calls.

| Cohort | Retrieval | Raw hit@5 → enriched hit@5 | Raw partial recall → enriched recall | Raw MRR → enriched MRR |
| --- | --- | --- | --- | --- |
| Pilot 24 | Keyword | 0.9583 → 0.9167 | 0.9375 → 0.9167 | 0.6458 → 0.6424 |
| Pilot 24 | Semantic | 0.9583 → 1.0000 | 0.9583 → 1.0000 | 0.7653 → 0.7896 |
| Pilot 24 | Hybrid | 1.0000 → 0.9583 | 1.0000 → 0.9583 | 0.7882 → 0.7708 |
| Hard 10 | Keyword | 0.3000 → 0.8000 | 0.3000 → 0.7500 | 0.2333 → 0.4750 |
| Hard 10 | Semantic | 0.2000 → 0.6000 | 0.2000 → 0.6000 | 0.2000 → 0.3583 |
| Hard 10 | Hybrid | 0.3000 → 0.9000 | 0.3000 → 0.9000 | 0.2250 → 0.5283 |

The raw scores match their preceding checkpoints. Enrichment substantially increases supplied-reference retrieval on the casual set but can distract ranking on already technical queries. Pilot hybrid loses the reference hit for P04; keyword also regresses. Hard hybrid gains H01, H04, H05, H06, H07 and H10, with H02 still missing. All input queries and positive references remain unchanged, and both modes remain available. This does not establish independent relevance accuracy, applicability, customer outcomes or repeat-fix rates for enriched generation; those require separate evaluation.
