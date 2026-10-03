# Monitoring and local measurements

Explain it this way: health tells us what is available, metrics tell us how the service is behaving, and labelled evaluations tell us whether its answers are useful. These are different questions.

- `/live` reports that the HTTP process responds. It does not contact the provider.
- `/ready` reports keyword readiness. `/ready?require_semantic=true` returns 503 until semantic search is loaded successfully. This explicit option prevents a keyword-only reviewer setup being treated as a failure.
- `/health` reports source types/counts, index version, lazy semantic state and provider configuration. Configuration is not proof that provider calls will succeed.
- Editor-only `/admin/metrics` reports request/error counts, in-flight requests, resolution/fallback counts, bounded latency samples, ingestion-job statuses and process RSS memory, cumulative CPU seconds and thread count.

Metrics use route templates rather than raw URLs and retain no complaint bodies, observations, keys or unmatched paths. Latency percentiles use the latest 256 samples per route, while counters cover the process lifetime. A metrics request is itself in flight when inspected. Counters reset on restart and are per process; deployments need an external collector and shared service dashboards.

`python benchmark_local.py` runs a repeatable small load check against FastAPI TestClient with 24 requests per mode and concurrency 4, using the real local model. It writes ignored `runtime/local-load-report.json`. It measures first hybrid request time separately from the warm requests and reports error counts, p50/p95, throughput and resources. It makes no LLM calls. It is an in-process measurement with cached weights, not network latency, production capacity or answer quality.

Operational checkpoints: compare warm/cold latency, investigate increasing fallback/error ratios, confirm ingestion failures leave readiness intact, and review memory as evidence grows. Alerts and targets should be set from actual deployment needs and repeated measurements, not from an invented SLA.

## Observed local checkpoint (3 October 2026)

One Windows run on 487 records, 24 requests per mode, concurrency 4, existing local weights:

| Mode | Errors | Warm p50 ms | Warm p95 ms | Requests/second |
| --- | ---: | ---: | ---: | ---: |
| Keyword | 0 | 194.79 | 277.25 | 19.25 |
| Semantic | 0 | 220.60 | 270.07 | 17.60 |
| Hybrid | 0 | 444.43 | 546.65 | 8.71 |

The first hybrid call took 30.11 seconds including process/model startup and initialization. End-of-run process RSS was about 537 MiB. These are observations from one small in-process run, not guaranteed performance. Hybrid does more work than either ranking alone; measured quality comparisons remain necessary to justify its cost. All 36 behavioural tests passed at this checkpoint, and the real-model temporary ingestion smoke check published version 2 while retaining version 1 citation evidence.
