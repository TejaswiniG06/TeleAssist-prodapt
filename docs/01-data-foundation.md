# Lesson 1 Data foundation

## Why we start with evidence

The language model writes a suggestion; the knowledge base supplies its justification. Poor reference material can produce a fluent but incorrect answer. Before building search, we define what evidence the system can use.

## Two source types

An article provides reusable diagnostic guidance with conditions and escalation rules. A resolved ticket records what happened in one particular case. A successful fix in one ticket is not a universal instruction.

The initial data contains three articles and two resolved tickets. The Wi-Fi category is currently represented only by a historical ticket; a dedicated article will be added during dataset expansion.

## Shared fields

| Field | Purpose |
| --- | --- |
| id | Stable identifier used in citations |
| record_type | Distinguishes articles from historical tickets |
| category | Issue label for organization; retrieval must not depend solely on perfect classification |
| product | Product applicability |
| version | Identifies a revision of the same source |
| status | Active records are searchable; retired records must be excluded |
| updated_at | Records when guidance changed |
| provenance | Identifies synthetic or external origin |

Category labels should be extensible. A complaint may remain unknown rather than being forced into a known label.

## Attempted actions need outcomes

The phrase 'I restarted' does not establish success or failure. We need action identity, outcome, and the complaint passage supporting that interpretation. We will support successful, failed, and unknown outcomes.

Action IDs normalize wording: 'rebooted the router' and 'restarted the router' can refer to restart_router. A controlled action vocabulary makes comparisons testable, but unfamiliar actions must still be representable.

## Walk through the evening-disconnection example

1. The complaint establishes an intermittent issue and a failed restart.
2. KB-001 supports asking about device scope and wired versus Wi-Fi behavior.
3. TICKET-001 demonstrates one historical Wi-Fi case, with observations missing from this new complaint.
4. The assistant should ask for those missing observations before recommending that historical fix.
5. It must not infer a confirmed cause simply because text is similar.

This is the distinction between similarity and applicability. It is central to our project contribution.

## Development examples are not final evaluation

evaluation_seed.json helps us develop and debug. Once we use these cases to tune the system, they are no longer a held-out test. We will create a separate evaluation set and freeze it before comparing final variants.

Expected sources help measure retrieval; acceptable and unacceptable behaviors help assess answers. We need both because good retrieval does not guarantee a good generated response.

## At production scale

Providers need guidance owners, approval workflows, access permissions, revision history, and retention rules. Search indexes are derived copies of authoritative records. Updating storage is insufficient unless the index is updated too. Later we will discuss retries, version checks, and deletion propagation.

## Interview checkpoint

You should be able to explain:

1. Why a resolved ticket is weaker evidence than a universally applicable instruction.
2. Why action identity alone is insufficient without an outcome.
3. Why valid citation IDs do not establish that the answer is supported.
4. Why development examples cannot also be treated as untouched final evaluation data.

Next lesson: turn these records into searchable text and implement keyword retrieval before introducing embeddings.
