# Evaluation and system checks

Results below use separate frozen development sets. They record earlier retrieval and generation runs; later state-clarification changes were covered by regression tests rather than a new full live benchmark. Software tests and citation membership do not establish customer outcomes.

## Retrieval pilot and live classification

The synthetic pilot queries below share vocabulary with the corpus. See [human-language evaluation](evaluation.md#casual-language-and-attempted-fix-comparison) for separately frozen casual/typo retrieval results, matched plain RAG repeated-fix comparison, product/category labels and mechanical citation pass rate. These cohorts must not be merged into one accuracy claim.

`python -m scripts.evaluation.evaluate_benchmark` compares keyword, semantic and hybrid on frozen `data/benchmark_v1.json`: 24 synthetic queries across broadband, mobile, fixed voice and IPTV. The development labels were derived from article scope before the first run. They are partial positive source references, not exhaustive relevance judgements or an independently blinded holdout. A canonical content hash test prevents silently changing pilot-v1 after seeing results; publish a new benchmark version for any label change.

All modes use the same 487-record base corpus, unfiltered queries, score threshold 0.30 and limit 20 before assessing the first five. The report records benchmark/corpus hashes and case-level IDs, so misses are inspectable. Metrics are reference hit@5, recall over the supplied partial references, and reciprocal rank of the first supplied reference within five. Unlabelled histories may be relevant and are not established negatives. These numbers do not measure answer success, citation entailment or customer outcomes.

### Frozen pilot results

| Mode | Reference hit@5 | Partial-reference recall@5 | Reference MRR@5 |
| --- | ---: | ---: | ---: |
| Keyword | 0.9583 | 0.9375 | 0.6458 |
| Semantic | 0.9583 | 0.9583 | 0.7653 |
| Hybrid | 1.0000 | 1.0000 | 0.7882 |

These are results on this small development-labelled synthetic pilot. They do not establish 100% real-world accuracy or universal superiority of hybrid. The [local performance measurement](#local-performance-measurement) shows hybrid's additional latency; compare quality and cost together.

Additional exploration: compare the top eight raw hybrid hits with product/trust-aware context selection. Both retained a supplied reference for all 24 cases. Mean unverified records were 0.708 versus 0.750 per context. This does **not** show fewer unverified records from trust selection: tier quotas explicitly retain some suggestions, and other relevant histories are incompletely labelled. The useful guarantee is labelled trust and domain filtering, not an unsupported claim that the ablation improves accuracy.

### Public complaints and safety checkpoints

`python -m scripts.evaluation.evaluate_public` uses 25 public complaint queries of unverified origin. It excludes the source ticket, identical complaints, and 3-word-shingle Jaccard near duplicates >=0.80. This is an explicit leakage heuristic, not comprehensive deduplication. Review near duplicates and label pooled candidate relevance/applicability independently before reporting public-query quality metrics. Candidate labels are still pending; the script reports no invented accuracy.

Behavioural tests cover missing/wrong role, stale updates, failed publication, retired records, embedding failure, provider failure, invented citations, suspicious source instructions, missing conditions, attempted restart aliases, unverified disclosure, masking, cluster review and split-service outages. `scripts/smoke/smoke_resolution.py` uses the configured free provider on synthetic inputs; it checks live classification/drafting, masking, no repeated restart, and cited source versions. Mechanical checks cannot replace manual applicability/entailment review.

Before final evaluation, have a reviewer confirm reference labels and annotate product/category/severity/sentiment, acceptable actions, required clarification, source applicability and unsafe suggestions. Freeze that independent benchmark before tuning. Report failures and denominators, not just a successful demo. Keep generated-history outcomes, public suggestions and provider-approved KB distinct. Current labels and thresholds are pilot settings, not production validation.

### Live classification and grounding results

`python -m scripts.evaluation.evaluate_classification` uses the same `Resolver.classify` method as drafting on six synthetic cases with author labels and explicit accepted category aliases. Gemini 3.5 Flash-Lite matched product, category and sentiment labels in 6/6 cases each, and severity in 2/6. It extracted the failed router restart in the applicable case. The four severity mismatches were model-inferred urgency where the author labels expected unknown. A provider-approved triage policy and independent adjudication are necessary before using those urgency labels operationally. The labels were not changed to hide the disagreement. These are diagnostic results, not validated classification accuracy.

The latest live resolution smoke check passed all three synthetic cases: a Wi-Fi draft cited KB-001 and TICKET-001 without another restart; a slow-speed case asked for clarification with no steps; a mobile no-signal case cited KB-GEN-007. Citation checks passed and the fake email was masked. A valid citation still needs applicability review; three examples are not an outcome-quality benchmark.


## Casual language and attempted-fix comparison

### Supported behaviour

The complaint classifier receives casual wording as text rather than requiring technical keywords. The provider still needs explicit evidence for an attempted action. Common router restart, airplane-mode, wired-comparison, speed-measurement, router-move and background-download aliases are normalized with a small rule table. Source instructions are normalized too, because generated records may use opaque action IDs. Every recognized attempted action is excluded from new steps, even when its outcome is unknown; clarification can ask about that outcome instead. Aliases are bounded patterns, not comprehensive language understanding.

Classification now includes churn_risk and churn_evidence. A narrow rule flags explicit first-person cancellation/leaving statements naming a service, contract, account, plan, subscription or provider. It does not infer churn from frustration, and does not detect every paraphrase. Severity remains a separate, unapproved triage suggestion. Both interfaces display explicit threats; the provider cannot invent a threat flag.

### Evaluation boundaries

The original synthetic retrieval queries share product names and vocabulary with the corpus. That makes them easier than independent customer language. Keep their results separate from the casual/typo challenge set. Queries and partial reference labels form a development challenge set, without independent human review. They were frozen before the first run; failures are retained and labels are not rewritten after observing results. This is not an independently reviewed holdout.

Repeated-fix rate needs both a numerator and a denominator: cases repeating at least one labelled attempted action / all attempted-action cases. Also report repetition among answers with steps, step-producing counts, provider fallbacks, extraction accuracy and whether a repeated action was actually available in retrieved evidence. A zero rate on unsupported/fallback-only cases does not show useful action selection.

### Reproduction and paired baseline

`python -m scripts.evaluation.evaluate_human_language` runs ten frozen casual/typo retrieval queries in all three modes, without provider calls. `--live` additionally runs the user's eight feature cases and five supplemental attempted-action cases. Three user cases plus five supplements form eight paired attempted-action complaints. `--export-summary` exports the completed measurements to data/human_language_results_v1.json; full masked result traces stay in ignored runtime storage. Query/label hashes are protected by tests. Provider calls use the existing confirmed-free configuration and 15-second spacing; there is no paid fallback.

The matched plain RAG baseline uses the same provider, temperature, masked context, hybrid candidate pools, product/trust selection, applicability prompt and citation checker. A shared classification is computed once and copied, with attempted actions removed for baseline drafting. The baseline wrapper removes only the no-repeat prompt; consequently its available options and checker do not exclude attempted actions. Execution order alternates. This isolates the attempted-action guard, not every difference between a naive free-form RAG system and TeleAssist. Both source context and classification are otherwise shared. A deterministic test additionally forces a repeated source action and verifies that the baseline accepts it while our guard excludes it.

Repetition is graded against frozen expected actions using independent instruction-wording patterns, including opaque source IDs. This is mechanical grading, not independent human semantic judgement. Action extraction succeeds only if every expected action is present. Provider/validation failures count as failed feature checks. An expected safe no-evidence abstention (weather) is a successful scope check, not a provider failure; no-step responses do not count as citation passes.

### Recorded result on 487 records

| Set | Mode | Reference hit@5 | Partial recall@5 | Reference MRR@5 |
| --- | --- | ---: | ---: | ---: |
| 10 casual/typo queries | Keyword | 0.30 | 0.30 | 0.2333 |
| 10 casual/typo queries | Semantic | 0.20 | 0.20 | 0.2000 |
| 10 casual/typo queries | Hybrid | 0.30 | 0.30 | 0.2250 |

H03 and H09 hit their references in every mode. H08 hits in keyword/hybrid only. H01/H02/H04/H05/H06/H07/H10 miss all supplied references within five. Labels were not rewritten after these misses. Similarities use the same 0.30 threshold as the original pilot. Other historical records might apply, so independent candidate relevance/applicability review is still necessary. The limited MiniLM model does not reliably recover the intended reference from very indirect wording. Future improvements should be tested on a new, independently reviewed set rather than rewriting this one.

| Eight paired complaints | Plain RAG | Our pipeline |
| --- | ---: | ---: |
| Repeated-fix cases | 1/8 (12.5%) | 0/8 (0%) |
| Answers with steps | 4/8 | 6/8 |
| Repetition among step-bearing answers | 1/4 (25%) | 0/6 (0%) |
| Provider / grounding failures | 0 / 0 | 0 / 0 |

Six contexts contained at least one expected attempted action among selected source options. R07 is the one baseline repeat: requesting a speed measurement already supplied by the customer. All eight cases remain in the denominator, including contexts without repeat opportunities. Extraction finds all expected actions in 7/8 cases; R08 misses the expected check_device_scope label. A zero observed repeat rate does not guarantee every paraphrase is extracted or protected.

Product/category labels matched in 8/8 each on user feature cases, and 13/13 product / 11/13 category on all feature/supplemental cases. R04 and R05 predicted "Wi-Fi coverage/interference", outside their frozen accepted category aliases. Those mismatches remain recorded; the aliases were not expanded to hide them. Six step-bearing responses passed source/version/action/quote checks (seven steps); seven no-step outcomes are excluded. These checks do not prove full applicability or customer resolution.

| User case | Observed outcome | Automated check |
| --- | --- | --- |
| U01: evening drops, router already restarted | Clarification | Restart extracted; no repeated restart; no churn threat |
| U02: phone/email/account in slow-fiber complaint | Clarification | All three identifiers absent from processed/provider payloads |
| U03: "internet not working properly" | Clarification | Questions, no steps |
| U04: "net keeps dying", box off/on | Cited draft | Broadband/connectivity; restart recognized and not repeated |
| U05: full 5G, airplane mode already tried | Cited draft | Mobile data; attempted toggle extracted; no broadband steps |
| U06: explicit cancellation threat | Clarification | Churn flag true with customer-text evidence |
| U07: instruction injection/refund/reset request | Clarification | No steps, refund promise or reset instruction emitted |
| U08: Chennai weather | Safe no-evidence clarification | Unknown product/category; no invented troubleshooting |

All eight pass these defined automated checks; this does not certify all wording, fault scenarios or draft applicability. Raw retrieval misses several casual-language references; the query-enrichment comparison below measures the subsequent improvement separately.

### Evidence Explorer and evolving-data checks

For "drops every evening", the recorded top five were:

| Mode | Source IDs in rank order |
| --- | --- |
| Keyword | SYN-04-20, SYN-05-20, SYN-07-01, SYN-01-07, SYN-07-09 |
| Semantic | TICKET-001, SYN-01-15, SYN-04-20, SYN-01-21, SYN-01-11 |
| Hybrid | SYN-04-20, TICKET-001, SYN-01-11, SYN-01-21, SYN-01-12 |

This shows different rankings, not an independently judged relevance comparison. The corpus does not promise actual device-model/error-code coverage. `python -m scripts.smoke.smoke_evolving_data` adds a clearly synthetic E-901 ONT article to an isolated real-model catalog, finds it directly with keyword and hybrid search, retires it and confirms exclusion from keyword/semantic/hybrid. Index versions progress 1 → 2 → 3 without a service restart. Version-1 evidence remains inspectable. The synthetic code is a retrieval/update test, not approved telecom guidance; the working catalog is untouched.


## Query-enrichment comparison

Previously resolution searched only the masked complaint and observations. It now appends the existing classification's product, category, normalized symptom phrases and normalized attempted-action names. This bridges casual customer wording to standard telecom vocabulary. Sentiment, severity and churn are omitted because they do not identify technical evidence. Unknown labels and duplicate metadata phrases are omitted. The final search text is masked and bounded to 2,000 characters, with at most 600 metadata characters. No synonym dictionary is fitted to evaluation reference IDs.

teleassist/retrieval/query.py is a pure string builder: it does not call a model, retrieve sources or choose a resolution. The classification schema now includes up to six short symptom phrases, extracted in the existing classification call. Resolution still makes its existing classification call and optional drafting call. There is no additional query-rewriting call.

### Comparable API modes

POST /resolve accepts query_mode="enriched" (default) or "raw". The dashboard's Resolution search query control exposes both. Raw retains the original masked-context query and the same maximum length. Single-process and separated resolution services reuse the same builder; upstream retrieval receives the already built query.

POST /search retains raw mode by default and never calls an LLM. To compare enriched retrieval directly, supply query_mode="enriched" and an existing Classification object. Enriched search without classification returns 422. Product/type filters, source exclusions, thresholds and ranking remain independent of query construction. Client-supplied metadata is a retrieval hint, not evidence or permission to bypass grounding. Evidence Explorer continues using key-free raw searches.

The original masked customer text is retained for drafting and exact applicability evidence checks. Inferred symptom phrases cannot establish that a customer condition is true. Tests force a phrase that occurs only in metadata and verify that a draft trying to cite it as customer evidence is rejected. Emerging-topic samples retain the original request text rather than appended classifier vocabulary.

### Paired evaluation

`python -m scripts.evaluation.evaluate_query_enrichment --refresh-classifications` creates or resumes predictions with the configured confirmed-free provider. There is one classification per frozen input, shared by keyword/semantic/hybrid raw and enriched searches. Only the query and allowed category schema reach classification; expected product labels and reference source IDs are never supplied. A failed classification falls back to local labels, remains in the denominator and is reported.

`python -m scripts.evaluation.evaluate_query_enrichment --replay-frozen-classifications` replays the committed historical prediction cache without any provider key. This reproduces retrieval using the earlier predictions; it does not evaluate the current classifier. The later prerequisite-clarification update changed classification, so the default command rejects the stale cache. Query fingerprints and taxonomy checks remain enforced in historical replay. The report records the historical classifier hash, query-builder hash, corpus hash and identical retrieval settings: 487 records, no product/type filter, 0.30 semantic threshold, limit 20 and assessment at five. The original 24-query pilot and 10-query casual/typo set stay frozen and separate. Both variants run in the same API instance. Rank settings, references and corpus are unchanged.

Snapshots in data/query_classifications_v1.json and data/query_enrichment_results_v1.json make the comparison reviewable without the author's credentials. These are cached provider predictions on development inputs, not independent human labels. Cached evaluation measures the retrieval change conditional on those predictions; live production quality still depends on classification correctness. Added context can help or distract retrieval, so regressions must be reported as well as improvements. Synthetic vocabulary overlap and incomplete reference labels remain limitations.

To reproduce the 487-record checkpoint from a fresh clone, run scripts/data/download_public.py first; without the optional pinned public candidates, the bundled corpus has 230 records and scores may differ. The report records the actual corpus count/hash. Code fingerprints normalize Git line endings for portable replay. Explicit refresh regenerates predictions if the classifier, taxonomy or provider/model changes; otherwise it resumes existing matching inputs.

### Recorded before/after results

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

## Local performance measurement

`python -m scripts.evaluation.benchmark_local` performs 24 requests per search mode at concurrency 4 with the real local model, using FastAPI TestClient. It writes ignored `runtime/local-load-report.json` and makes no provider calls. This measures in-process performance rather than network latency or deployment capacity.


One Windows run on 487 records, 24 requests per mode, concurrency 4, existing local weights:

| Mode | Errors | Warm p50 ms | Warm p95 ms | Requests/second |
| --- | ---: | ---: | ---: | ---: |
| Keyword | 0 | 194.79 | 277.25 | 19.25 |
| Semantic | 0 | 220.60 | 270.07 | 17.60 |
| Hybrid | 0 | 444.43 | 546.65 | 8.71 |

The first hybrid call took 30.11 seconds including process/model startup and initialization. End-of-run process RSS was about 537 MiB. These are observations from one small in-process run, not guaranteed performance. Hybrid does more work than either ranking alone; measured quality comparisons remain necessary to justify its cost.

## Software and integration checks

The current recorded suite has 113 passing unit, integration and UI tests. Run `python -m unittest discover -s tests -q` for the current checkout. Tests cover retrieval/cache behaviour, masking, roles, citations, attempted actions, clarification continuation, version conflicts, publication recovery, topic review and service failures. No-key UI coverage verifies that search and saving remain available; launcher checks distinguish access errors, model unavailability, timeouts and connection failures.

| Command | Checks | Provider calls |
| --- | --- | --- |
| `python -m scripts.smoke.smoke_services` | Real local MiniLM and API integration | No |
| `python -m scripts.smoke.smoke_split` | Independent HTTP services, publication, historical versions and outage handling | No |
| `python -m scripts.smoke.smoke_case_feedback` | Pending case exclusion, reviewed publication and restart recovery | No |
| `python -m scripts.smoke.smoke_evolving_data` | Add/search/retire an isolated source without restart | No |
| `python -m scripts.smoke.smoke_resolution` | Live classification, masking and cited drafting | Yes |

Smoke checks use isolated demonstration storage where appropriate. Saving, outcome recording and editor publication need no model call. Earlier browser checks covered light/dark contrast, narrow layouts and reduced motion; Streamlit tests also render API responses. These checks verify functionality and presentation, while broader independent applicability and topic-quality review remain future work.
