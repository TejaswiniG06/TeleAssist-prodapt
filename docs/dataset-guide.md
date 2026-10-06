# Dataset guide

TeleAssist searches knowledge-base articles and historical tickets. Articles provide reusable guidance; tickets record actions and outcomes from individual cases. A successful historical action does not prove that it applies to a new complaint.

## Bundled and optional sources

The repository contains 230 synthetic records: 28 KB articles, 162 resolved histories and 40 unresolved histories. The optional pinned public download adds 257 unverified tickets, giving the 487-record evaluation corpus. Synthetic outcomes describe demonstration scenarios, not real customer confirmations. Public replies have unknown outcomes and retain attribution and licence information.

Selection and provenance are documented below. See [architecture](architecture.md#classification-current-state-and-grounding) for evidence-tier handling and the [README](../README.md#run-locally) for setup.

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

An evening-disconnection complaint may retrieve KB-001 and TICKET-001. Before using their actions, the system needs relevant observations such as device scope and wired versus Wi-Fi behaviour. A matching symptom, high retrieval rank or valid citation ID alone does not establish a cause or prove that a source condition holds.

## Evaluation and maintenance

`data/evaluation_seed.json` contains development examples. Frozen pilot and casual-language query sets are separate, but their labels still lack independent review. Retrieval and answer applicability must be evaluated separately; good retrieval does not guarantee a useful resolution.

Editor updates build a replacement index before publication. Retired records leave current search, while historical versions remain available for citations. Production use requires approved guidance owners, retention policies and shared durable storage. See [background evidence updates](architecture.md#background-evidence-updates).

## Public dataset provenance


Source: https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets
Creator attribution: Tobi-Bueck / Softoft. Dataset card declares CC-BY-NC-4.0 and advertises a synthetic-ticket generator. That advertisement does not establish the origin of every downloaded complaint; the adapter now records `public_origin_unverified`. This is educational, noncommercial inspection; do not treat this licence as commercial deployment permission.

Inspected `aa_dataset-tickets-multi-lang-5-2-50-version.csv`, SHA256 `f187c090e59581c2bbf3aa1377c8db4dd647464ecf2ae51bf8966e42e0ed6bc0`. This file contains 28,587 rows: 16,338 English and 12,249 German. These counts describe this file, not all files in the dataset repository.

Columns: subject, body, answer, type, queue, priority, language, version, tag_1 through tag_8. Priority is a source label, not a verified telecom severity. An agent answer is not proof of a successful resolution; there is no customer-confirmed outcome field.

`scripts/data/prepare_tickets.py` selects English rows with explicit telecom/network terms in subject/body, deduplicates by text hash, and retains source rows, original labels, licence, attribution, and match terms. It produced 257 candidates. Raw data and candidate text remain in ignored scratch storage. No external answer was promoted into the active knowledge base.

The stricter terms broadband, telecom, mobile network, SIM card, VoIP, internet service, fiber/fibre, 4G, and 5G matched none of those candidates. The broader matches are largely router, Wi-Fi, modem, or internet-connection references. Manual inspection of rows 12, 42, 74, 179, 183 and 245 found VPN infrastructure, doorbell integration, NAS connectivity, adapter/OS compatibility, analytics integration, and smart-camera connectivity. These are adjacent IT/device problems, not verified telecom service fixes. Row 245's answer even assumes dual-band router capability without the complaint establishing it.

Selection decision: index all 257 as lower-trust `unverified_ticket` evidence. Similar replies may inform an explicitly qualified suggestion, never a confirmed historical fix. Synthetic history with explicit outcomes and an expanded KB supplements these records. Nonresolved history cannot supply successful fixes. The additional conversation-corpus inspection is summarized below; provider-approved policy evidence remains future work.

Twenty-five public complaint texts are reserved as query-only evaluation cases, with their original indexed record excluded during evaluation. These are public-language queries of unverified origin, not confirmed real customer data. Manual relevance labels and near-duplicate review remain necessary before reporting quality metrics. Source attribution and licence are retained.

## Reproducible optional public setup

Run `python -m scripts.data.download_public`. It downloads the audited CSV from revision `ddf1c81a5475992c4fa6752bf1e8b4e31f07bbeb`, verifies SHA256 `f187c090e59581c2bbf3aa1377c8db4dd647464ecf2ae51bf8966e42e0ed6bc0`, and runs the existing filter. The [source file page](https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets/blob/ddf1c81a5475992c4fa6752bf1e8b4e31f07bbeb/aa_dataset-tickets-multi-lang-5-2-50-version.csv) exposes the file/hash; dataset attribution and CC-BY-NC-4.0 remain unchanged. Checksum mismatch preserves previous data. Re-running reuses a matching local file. Raw/candidate data stay ignored, and held-out query labels are not regenerated.


## Sources inspected but not indexed

The suggested [municipal ticket dataset](https://github.com/santhoshmishra/Ticket_data) contains 25,921 records, including noise, parking, street and sanitation complaints. It does not match telecom support; no licence file was found during inspection. It was excluded from grounding and is not redistributed.

The [Telecom Conversation Corpus](https://huggingface.co/datasets/talkmap/telecom-conversation-corpus) describes synthetic conversations with MIT licensing. A bounded inspection covered 100 utterances across seven conversations. Its utterance schema has no explicit confirmed-resolution outcome and includes provider-specific dialogue. It was not imported as resolved history. A future adapter would need conversation reconstruction and separate outcome/policy review.

## Corpus preparation

`python -m scripts.data.prepare_tickets scratch/tobi-tickets.csv` filters and reports public candidates. `python -m scripts.data.generate_corpus` uses a locally configured confirmed-free provider to request eight batches of 25 histories (160 resolved and 40 unresolved), plus an article batch reaching 28 KB articles. Two starter resolved histories bring the total resolved count to 162.

Batch validation rejects malformed records, exact duplicates and supported PII patterns; incomplete batches are not published. Intermediate batches stay in ignored runtime storage, and final output records provider/model, counts and a checksum. Schema validation does not establish technical correctness or diversity. Bundled guidance is synthetic demonstration evidence rather than provider-approved policy.
