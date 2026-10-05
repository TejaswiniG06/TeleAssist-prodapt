# Repeatable evaluation and honest interpretation

The synthetic pilot queries below share vocabulary with the corpus. See [human-language evaluation](12-human-language-evaluation.md) for separately frozen casual/typo retrieval results, matched plain RAG repeated-fix comparison, product/category labels and mechanical citation pass rate. These cohorts must not be merged into one accuracy claim.

`python -m scripts.evaluation.evaluate_benchmark` compares keyword, semantic and hybrid on frozen `data/benchmark_v1.json`: 24 fictional queries across broadband, mobile, fixed voice and IPTV. The labels were authored with AI assistance from article scope before the first run. They are partial positive source references, not exhaustive relevance judgements or an independently blinded holdout. A canonical content hash test prevents silently changing pilot-v1 after seeing results; publish a new benchmark version for any label change.

All modes use the same 487-record base corpus, unfiltered queries, score threshold 0.30 and limit 20 before assessing the first five. The report records benchmark/corpus hashes and case-level IDs, so misses are inspectable. Metrics are reference hit@5, recall over the supplied partial references, and reciprocal rank of the first supplied reference within five. Unlabelled histories may be relevant and are not established negatives. These numbers do not measure answer success, citation entailment or customer outcomes.

## Observed frozen pilot checkpoint

| Mode | Reference hit@5 | Partial-reference recall@5 | Reference MRR@5 |
| --- | ---: | ---: | ---: |
| Keyword | 0.9583 | 0.9375 | 0.6458 |
| Semantic | 0.9583 | 0.9583 | 0.7653 |
| Hybrid | 1.0000 | 1.0000 | 0.7882 |

These are results on this small author-labelled synthetic pilot. They do not establish 100% real-world accuracy or universal superiority of hybrid. The load checkpoint in docs/07-monitoring.md shows hybrid's additional latency; compare quality and cost together.

Additional exploration: compare the top eight raw hybrid hits with product/trust-aware context selection. Both retained a supplied reference for all 24 cases. Mean unverified records were 0.708 versus 0.750 per context. This does **not** show fewer unverified records from trust selection: tier quotas explicitly retain some suggestions, and other relevant histories are incompletely labelled. The useful guarantee is labelled trust and domain filtering, not an unsupported claim that the ablation improves accuracy.

## Public complaints and safety checkpoints

`python -m scripts.evaluation.evaluate_public` uses 25 public complaint queries of unverified origin. It excludes the source ticket, identical complaints, and 3-word-shingle Jaccard near duplicates >=0.80. This is an explicit leakage heuristic, not comprehensive deduplication. Review near duplicates and label pooled candidate relevance/applicability independently before reporting public-query quality metrics. Candidate labels are still pending; the script reports no invented accuracy.

Behavioural tests cover missing/wrong role, stale updates, failed publication, retired records, embedding failure, provider failure, invented citations, suspicious source instructions, missing conditions, attempted restart aliases, unverified disclosure, masking, cluster review and split-service outages. `scripts/smoke/smoke_resolution.py` uses the configured free provider on fictional inputs; it checks live classification/drafting, masking, no repeated restart, and cited source versions. Mechanical checks cannot replace manual applicability/entailment review.

Before final evaluation, have a reviewer confirm reference labels and annotate product/category/severity/sentiment, acceptable actions, required clarification, source applicability and unsafe suggestions. Freeze that independent benchmark before tuning. Report failures and denominators, not just a successful demo. Keep generated-history outcomes, public suggestions and provider-approved KB distinct. Current labels and thresholds are pilot settings, not production validation.

## Live classification and grounding checkpoint

`python -m scripts.evaluation.evaluate_classification` uses the same `Resolver.classify` method as drafting on six fictional cases with author labels and explicit accepted category aliases. Gemini 3.5 Flash-Lite matched product, category and sentiment labels in 6/6 cases each, and severity in 2/6. It extracted the failed router restart in the applicable case. The four severity mismatches were model-inferred urgency where the author labels expected unknown. A provider-approved triage policy and independent adjudication are necessary before using those urgency labels operationally. The labels were not changed to hide the disagreement. These are diagnostic results, not validated classification accuracy.

The latest live resolution smoke check passed all three fictional cases: a Wi-Fi draft cited KB-001 and TICKET-001 without another restart; a slow-speed case asked for clarification with no steps; a mobile no-signal case cited KB-GEN-007. Citation checks passed and the fake email was masked. A valid citation still needs applicability review; three examples are not an outcome-quality benchmark.
