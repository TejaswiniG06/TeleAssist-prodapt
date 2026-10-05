# Human language and attempted-fix evaluation

## Supported behaviour

The complaint classifier receives casual wording as text rather than requiring technical keywords. The provider still needs explicit evidence for an attempted action. Common router restart, airplane-mode, wired-comparison, speed-measurement, router-move and background-download aliases are normalized with a small rule table. Source instructions are normalized too, because generated records may use opaque action IDs. Every explicitly attempted action is excluded from new steps, even when its outcome is unknown; clarification can ask about that outcome instead. Aliases are bounded patterns, not comprehensive language understanding.

Classification now includes churn_risk and churn_evidence. A narrow rule flags explicit first-person cancellation/leaving statements naming a service, contract, account, plan, subscription or provider. It does not infer churn from frustration, and does not detect every paraphrase. Severity remains a separate, unapproved triage suggestion. Both interfaces display explicit threats; the provider cannot invent a threat flag.

## Evaluation boundaries

The original synthetic retrieval queries share product names and vocabulary with the corpus. That makes them easier than independent customer language. Keep their results separate from the casual/typo challenge set. Queries and reference labels are manually composed by the coding assistant, not independently authored/adjudicated by a human; they must not be advertised as a human-reviewed holdout. Freeze them before the first run, retain failures and do not rewrite labels after observing results.

Repeated-fix rate needs both a numerator and a denominator: cases repeating at least one labelled attempted action / all attempted-action cases. Also report repetition among answers with steps, step-producing counts, provider fallbacks, extraction accuracy and whether a repeated action was actually available in retrieved evidence. A zero rate on unsupported/fallback-only cases does not show useful action selection.

## Reproduction and paired baseline

`python -m scripts.evaluation.evaluate_human_language` runs ten frozen casual/typo retrieval queries in all three modes, without provider calls. `--live` additionally runs the user's eight feature cases and five supplemental attempted-action cases. Three user cases plus five supplements form eight paired attempted-action complaints. `--export-summary` exports the completed measurements to data/human_language_results_v1.json; full masked result traces stay in ignored runtime storage. Query/label hashes are protected by tests. Provider calls use the existing confirmed-free configuration and 15-second spacing; there is no paid fallback.

The matched plain RAG baseline uses the same provider, temperature, masked context, hybrid candidate pools, product/trust selection, applicability prompt and citation checker. A shared classification is computed once and copied, with attempted actions removed for baseline drafting. The baseline wrapper removes only the no-repeat prompt; consequently its available options and checker do not exclude attempted actions. Execution order alternates. This isolates the attempted-action guard, not every difference between a naive free-form RAG system and TeleAssist. Both source context and classification are otherwise shared. A deterministic test additionally forces a repeated source action and verifies that the baseline accepts it while our guard excludes it.

Repetition is graded against frozen expected actions using independent instruction-wording patterns, including opaque source IDs. This is mechanical grading, not independent human semantic judgement. Action extraction succeeds only if every expected action is present. Provider/validation failures count as failed feature checks. An expected safe no-evidence abstention (weather) is a successful scope check, not a provider failure; no-step responses do not count as citation passes.

## Recorded result on 487 records

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

All eight pass these defined automated checks; this does not certify all wording, fault scenarios or draft applicability. For example, very casual evidence retrieval remains weak despite successful classification of the feature examples.

## Evidence Explorer and evolving-data checks

For "drops every evening", the recorded top five were:

| Mode | Source IDs in rank order |
| --- | --- |
| Keyword | SYN-04-20, SYN-05-20, SYN-07-01, SYN-01-07, SYN-07-09 |
| Semantic | TICKET-001, SYN-01-15, SYN-04-20, SYN-01-21, SYN-01-11 |
| Hybrid | SYN-04-20, TICKET-001, SYN-01-11, SYN-01-21, SYN-01-12 |

This shows different rankings, not an independently judged relevance comparison. The corpus does not promise actual device-model/error-code coverage. `python -m scripts.smoke.smoke_evolving_data` adds a clearly synthetic E-901 ONT article to an isolated real-model catalog, finds it directly with keyword and hybrid search, retires it and confirms exclusion from keyword/semantic/hybrid. Index versions progress 1 → 2 → 3 without a service restart. Version-1 evidence remains inspectable. The fictional code is a retrieval/update test, not approved telecom guidance; the working catalog is untouched.
