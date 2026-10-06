# Evidence data and schema

TeleAssist searches knowledge-base articles and historical tickets. Articles provide reusable guidance; tickets record actions and outcomes from individual cases. A successful historical action does not prove that it applies to a new complaint.

## Bundled and optional sources

The repository contains 230 synthetic records: 28 KB articles, 162 resolved histories and 40 unresolved histories. The optional pinned public download adds 257 unverified tickets, giving the 487-record evaluation corpus. Synthetic outcomes describe demonstration scenarios, not real customer confirmations. Public replies have unknown outcomes and retain attribution and licence information.

See [dataset audit](dataset-audit.md) for selection and provenance, and [trust and resolution](03-trust-and-resolution.md) for evidence-tier handling. The README documents the pinned public download.

## Shared fields

| Field | Purpose |
| --- | --- |
| `id` | Stable source reference used in citations |
| `record_type` | Article, resolved ticket, unresolved ticket or unverified ticket |
| `product`, `category` | Applicability and issue labels |
| `version` | Source revision; citations retain the exact version |
| `status` | Active or retired; retirement removes the record from current search |
| `provenance`, `evidence_tier` | Source origin and trust label |
| `steps` or `resolution_steps` | Action IDs, source instructions and applicability conditions |
| `outcome`, `outcome_evidence` | Reported historical result and supporting description |

## Actions, outcomes and current state

Attempted actions include an action ID, an outcome (`successful`, `failed` or `unknown`) and an exact customer quote. Common aliases normalize to the same action ID. Recognized attempts are excluded before step selection, including attempts with unknown outcomes.

An attempted action does not establish current state. Removing a SIM does not establish reinsertion; unplugging a cable does not establish reconnection. State checks ask for missing information and use clarification answers without treating a negative answer as a completed repair.

## Similarity and applicability

An evening-disconnection complaint can retrieve KB-001 and TICKET-001. Before using their actions, the system needs relevant observations such as device scope and wired versus Wi-Fi behaviour. A matching symptom, high retrieval rank or valid citation ID alone does not establish a cause or prove that a source condition holds.

## Evaluation and maintenance

`data/evaluation_seed.json` contains development examples. Frozen pilot and casual-language query sets are separate, but their labels still lack independent review. Retrieval and answer applicability must be evaluated separately; good retrieval does not guarantee a useful resolution.

Editor updates build a replacement index before publication. Retired records leave current search, while historical versions remain available for citations. Production use requires approved guidance owners, retention policies and shared durable storage. See [access and updates](06-access-and-updates.md).
