# Design decisions and tradeoffs

The prototype turns a complaint into a reviewed, source-backed draft. It preserves both knowledge articles and historical tickets, labels uncertainty, and asks for clarification when a checked draft is unavailable.

| Choice | Why | Limit or alternative |
| --- | --- | --- |
| FastAPI with small Python modules | Input validation and clear boundaries between HTTP, retrieval and grounding | No infrastructure-level scaling guarantee |
| BM25 baseline | Explainable exact-term matching with no provider dependency | Can miss paraphrases |
| Local MiniLM semantic retrieval | Meaning-based retrieval without a paid embedding API | Cold startup and memory cost; domain adaptation needs evaluation |
| RRF hybrid ranking | Combine complementary rankings without mixing incompatible scores | Adds latency; fixed settings require measured validation |
| Classification-aware query construction | Reuse product/category/symptoms/actions to bridge casual wording without another LLM call | May distract technical-query ranking; retain raw mode and paired measurements |
| Explicit evidence tiers and provenance | Include public replies without claiming confirmed outcomes; distinguish synthetic history | Trust does not prove relevance or applicability |
| Source-selected actions and citation checks | Trace proposed actions to exact source versions and avoid unsupported steps | Mechanical checks do not prove complete semantic entailment |
| Attempted-action awareness | Avoid repeating failed or completed actions | Extraction and aliases can miss wording; agent review remains necessary |
| Clarification and escalation | Fail visibly when conditions, evidence or dependencies are insufficient | Measure abstention quality as well as answer quality |
| Agent/editor application roles | Separate case handling from shared evidence/taxonomy changes | Shared API keys are prototype access, not enterprise identity |
| Background index replacement | Readers keep the old version until a validated replacement is published | File storage and publication are single-writer |
| Human-reviewed lexical topic proposals | Explainable emerging-topic signals without automatic fixes | Similar language is not proof of a new fault |
| Bounded per-process metrics | Inspect latency, errors, outcomes and resources without complaint logging | Restart resets counters; production needs external collection |
| Default separate retrieval/resolution services | Demonstrate real HTTP boundaries while retaining easy local setup | Horizontal scaling requires shared version storage, durable jobs and distributed quotas |
| Independent case submissions | Simple workflow with explicit observations and attempted actions | No chatbot memory; each request supplies all required context |
| Separate Streamlit Case workspace | Python-native forms/top navigation call the real FastAPI API; presentation and decisions stay separate | Additional process/dependency; native layout rather than pixel-exact preview styling |


## Evidence for the choices

The [evaluation report](evaluation.md) includes the 24-query pilot, ten casual-language queries, paired attempted-fix comparison, classification/citation checks and local latency measurements. Query enrichment improves the casual set but regresses some pilot rankings; raw mode remains available. These are small development sets rather than independent production validation.

## Production-scale considerations

The catalog supports one writer. Multiple workers require shared versioned storage, a durable ingestion queue, coordinated publication and provider quotas. Shared application keys should be replaced with per-user identity for public use. Production also requires TLS, encryption, backups, retention controls and capacity measurements. A vector database is justified by measured needs rather than by the microservice requirement itself.

See the [architecture deployment path](architecture.md#production-deployment-path) and [deployment guide](deployment.md) for the implemented boundaries and remaining work.
