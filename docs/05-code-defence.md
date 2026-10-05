# Explain and defend the core

Start with the flow: complaint → mask common identifiers → classify and identify attempted actions → retrieve relevant evidence → choose supported actions → check citations → draft or clarify. The browser displays these decisions; it does not decide a fix or receive the API key.

| File | Responsibility | How to explain the choice | Limit to acknowledge |
| --- | --- | --- | --- |
| teleassist/common/privacy.py | Mask common identifiers | Reduce exposed identifiers before retrieval and provider calls | Patterns do not recognize every name, address or secret |
| teleassist/retrieval/keyword.py | BM25 keyword search | Establish an inexpensive exact-term baseline | Different wording can miss relevant records |
| teleassist/retrieval/semantic.py | Local vectors, cosine similarity, rank fusion | Match meaning locally; combine two rankings with RRF | Similarity and fusion are retrieval signals, not proof a fix applies |
| teleassist/retrieval/evidence.py | Load evidence and preserve trust/provenance | Include past suggestions honestly without assuming successful outcomes | Synthetic outcomes are scenario labels; public outcomes are unknown |
| teleassist/resolution/llm.py | Free provider calls and structured JSON | One provider, explicit configuration, bounded retry and pacing | Free quotas can interrupt generation; fallback is necessary |
| teleassist/resolution/pipeline.py | Classify, select and check steps | Use source-backed actions and avoid repeating completed/failed actions | Exact quote and customer-text checks cannot establish full semantic entailment |
| teleassist/services/ | Validate HTTP inputs and expose two services | Separate service processes call over HTTP; shared schemas avoid duplicate validation | Retrieval state is single-writer; service separation does not prove horizontal capacity |
| web/index.html | Agent review interface | A single page calls the API and exposes evidence | Agent review is still required |
| frontend/app.py, frontend/views/, frontend/client.py | Case workspace screens and HTTP client | Separate Python presentation calls the real API; no duplicated decision logic | Extra process; API keys are prototype roles, not individual identities |

## Why the source filter was simplified

Previously api.py constructed a SemanticIndex with `__new__` and manually assigned its fields. That bypassed normal initialization and made the API responsible for index internals. Now the API supplies an explicit set of allowed source IDs. SemanticIndex skips excluded records before scoring/ranking; HybridIndex applies the same restriction to the keyword pool before rank fusion. Existing source vectors remain cached and unchanged.

Explain this as: **choose eligible sources first, rank those sources second, return the best matches last.** Filtering only after taking the top results could lose valid matches when excluded sources dominate the rankings. A test uses 25 matching sources and permits only the final one, ensuring it still returns with limit 1. It also checks that filtering reuses source embeddings rather than encoding the corpus again.

## Interview questions

- **Why hybrid?** Exact terms and paraphrases are complementary; keep BM25 as a baseline and measure whether hybrid improves labelled retrieval. Do not claim superiority before evaluation.
- **Why synthetic tickets?** The brief permits them, and they provide explicit steps/outcomes unavailable in public replies. Label them visibly and report evaluation limits.
- **Why retain public tickets?** They add complaint variety and suggested past responses. Their lower trust and unknown outcomes must remain explicit.
- **Why clarification?** Missing conditions, unsupported steps and provider failures should not produce a confident unchecked fix.
- **Is it production ready?** Access roles, versioned updates, monitoring and local capacity/quality pilots are implemented. External identity, shared storage/queues, coordinated quotas and independent quality validation remain outstanding.
- **Is it unique?** The useful combination is trust-aware historical grounding plus attempted-action handling and inspectable evidence. The underlying retrieval techniques are established.

Keep functions organized around these responsibilities. Simplify indirection when it obscures the flow, but retain validation, failure handling and meaningful tests. The completed cleanup groups implementations by responsibility and retains the existing startup entry points. See [project structure](16-project-structure.md).
