# Design decisions and tradeoffs

The prototype turns a complaint into a reviewed, source-backed draft. It preserves both knowledge articles and historical tickets, labels uncertainty, and asks for clarification when a checked draft is unavailable.

| Choice | Why | Limit or alternative |
| --- | --- | --- |
| FastAPI with small Python modules | Input validation and clear boundaries between HTTP, retrieval and grounding | No infrastructure-level scaling guarantee |
| BM25 baseline | Explainable exact-term matching with no provider dependency | Can miss paraphrases |
| Local MiniLM semantic retrieval | Meaning-based retrieval without a paid embedding API | Cold startup and memory cost; domain adaptation needs evaluation |
| RRF hybrid ranking | Combine complementary rankings without mixing incompatible scores | Adds latency; fixed settings require measured validation |
| Explicit evidence tiers and provenance | Include public replies without claiming confirmed outcomes; distinguish synthetic history | Trust does not prove relevance or applicability |
| Source-selected actions and citation checks | Trace proposed actions to exact source versions and avoid unsupported steps | Mechanical checks do not prove complete semantic entailment |
| Attempted-action awareness | Avoid repeating failed or completed actions | Extraction and aliases can miss wording; agent review remains necessary |
| Clarification and escalation | Fail visibly when conditions, evidence or dependencies are insufficient | Measure abstention quality as well as answer quality |
| Agent/editor application roles | Separate case handling from shared evidence/taxonomy changes | Shared API keys are prototype access, not enterprise identity |
| Background index replacement | Readers keep the old version until a validated replacement is published | File storage and publication are single-writer |
| Human-reviewed lexical topic proposals | Explainable emerging-topic signals without automatic fixes | Similar language is not proof of a new fault |
| Bounded per-process metrics | Inspect latency, errors, outcomes and resources without complaint logging | Restart resets counters; production needs external collection |
| Optional separate retrieval/resolution services | Demonstrate real HTTP boundaries while retaining easy local setup | Horizontal scaling requires shared version storage, durable jobs and distributed quotas |
| Independent case submissions | Simple workflow with explicit observations and attempted actions | No chatbot memory; each request supplies all required context |

## Evaluation evidence

The frozen 24-query, AI-assisted partial-reference pilot on 487 records measured:

| Mode | Reference hit@5 | Partial-reference recall@5 | Reference MRR@5 |
| --- | ---: | ---: | ---: |
| Keyword | 0.9583 | 0.9375 | 0.6458 |
| Semantic | 0.9583 | 0.9583 | 0.7653 |
| Hybrid | 1.0000 | 1.0000 | 0.7882 |

These are development pilot results, not real-world accuracy. Six live classification cases matched product/category/sentiment in 6/6 each and severity in 2/6. Severity policy and independent label review remain pending. Public queries have self/near-duplicate exclusions but no independently reviewed relevance score. See [evaluation](10-evaluation.md) and [local latency measurements](07-monitoring.md).

## Production-scale considerations

The executable prototype supports a single catalog writer. Running more workers against its files is unsafe. Before production, introduce shared versioned storage, a durable ingestion queue, coordinated publication and provider quotas, external identity, encrypted transport/storage, backups and retention policies. Choose a vector database only when measured corpus size, memory or query rate justifies it. Free generation quotas are a dependency constraint, not a throughput promise.

The [architecture production deployment section](architecture.md#production-deployment-path--beyond-the-local-prototype) includes the proposed diagram. The [deployment walkthrough](09-service-deployment.md) distinguishes the executable split mode from the remaining scale work.
