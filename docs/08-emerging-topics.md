# Emerging topics and reviewed taxonomy

Explain it this way: repeated weak matches suggest that the existing evidence may miss a topic. The system groups similar complaints and asks an editor to review a proposed category; it never invents a fix from a cluster.

Unfiltered search records weak semantic/hybrid matches below 0.40, or keyword searches with no matches. These are heuristics, not a calibrated novelty model. Resolution also records no-applicable-evidence fallbacks. Provider outages or missing keys do not count as topic novelty. Deliberately filtered/excluded searches and increased score thresholds are excluded from this signal.

The monitor stores up to 200 distinct pattern-masked complaints. Repeated identical text increments occurrences but does not supply independent cluster members. It uses TF-IDF word/bigram vectors and cosine similarity >=0.35 to link complaints; connected groups with at least three distinct members become proposals. Top weighted terms and up to three examples help review. Thresholds are explicit defaults needing evaluation. Single-link grouping can bridge related groups, and vocabulary overlap can miss paraphrases; this is intentionally a small, explainable baseline.

Editor APIs: `GET /admin/topics` lists proposals; `POST /admin/topics/replay` replays up to 50 fictional/historical complaints through hybrid search; `POST /admin/topics/{id}/review` approves a new category or rejects a proposal with a rationale. `GET /taxonomy` exposes initial corpus categories plus reviewed approvals. Classification receives that finite category list; unsupported generated labels become unknown. Evidence ingestion rejects new categories until approved. Approval changes only taxonomy, never adds resolution evidence.

Proposal IDs derive from member IDs. Changed membership can produce a new proposal for review; existing approvals remain in taxonomy. Reviews are immutable in this prototype and contain role, UTC time and masked rationale. Samples/reviews persist in ignored `runtime/topic_state.json`. Search remains usable if sample persistence fails and the report shows storage degradation; approval fails without changing taxonomy if it cannot persist.

Pattern masking is not comprehensive anonymization. Do not replay real private complaints in the educational demo. Production needs retention controls, per-user audit identity, scheduled clustering over larger windows and reviewed quality measurements. Synthetic satellite examples in tests demonstrate the grouping mechanism; they do not establish telecom-domain topic quality.
