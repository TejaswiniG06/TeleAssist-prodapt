# Suggested dataset inspection

Source: https://github.com/santhoshmishra/Ticket_data

Inspected data/tickets.csv on 2026-10-03. The downloaded file is retained in the workspace scratch directory, not redistributed with the project.

## Findings

25,921 records. Columns: ticket_id, created_date, closed_date, agency, complaint_type, descriptor, borough, status, resolution_description. 22,760 rows have nonempty resolution descriptions.

The observed categories are municipal complaints: residential noise, illegal parking, street conditions, rodents, heat/hot water, sanitation, and water systems. Agencies include NYPD, DOT, DOHMH, HPD, DSNY, and DEP. This is not telecom support data.

Observed resolution descriptions include an unsuccessful inspection visit, no rodent activity found, and a police report prepared. Nonempty resolution text or a closed status does not establish a successful technical fix.

No licence file was present in the inspected repository tree. Redistribution or reuse terms remain unverified.

## Decision

Do not silently transform these municipal records into factual telecom resolutions. The data can inform adapter/schema experiments, subject to reuse terms, but it is unsuitable as authoritative telecom grounding. Inspect the suggested Telecom Conversation Corpus next and supplement missing resolution evidence with clearly labelled synthetic telecom records, as permitted by the brief.

## Tobi-Bueck support tickets (2026-10-03)

Source: https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets
Creator attribution: Tobi-Bueck / Softoft. Dataset card declares CC-BY-NC-4.0 and advertises a synthetic-ticket generator. That advertisement does not establish the origin of every downloaded complaint; the adapter now records `public_origin_unverified`. This is educational, noncommercial inspection; do not treat this licence as commercial deployment permission.

Inspected `aa_dataset-tickets-multi-lang-5-2-50-version.csv`, SHA256 `f187c090e59581c2bbf3aa1377c8db4dd647464ecf2ae51bf8966e42e0ed6bc0`. This file contains 28,587 rows: 16,338 English and 12,249 German. These counts describe this file, not all files in the dataset repository.

Columns: subject, body, answer, type, queue, priority, language, version, tag_1 through tag_8. Priority is a source label, not a verified telecom severity. An agent answer is not proof of a successful resolution; there is no customer-confirmed outcome field.

`prepare_tickets.py` selects English rows with explicit telecom/network terms in subject/body, deduplicates by text hash, and retains source rows, original labels, licence, attribution, and match terms. It produced 257 candidates. Raw data and candidate text remain in ignored scratch storage. No external answer was promoted into the active knowledge base.

The stricter terms broadband, telecom, mobile network, SIM card, VoIP, internet service, fiber/fibre, 4G, and 5G matched none of those candidates. The broader matches are largely router, Wi-Fi, modem, or internet-connection references. Manual inspection of rows 12, 42, 74, 179, 183 and 245 found VPN infrastructure, doorbell integration, NAS connectivity, adapter/OS compatibility, analytics integration, and smart-camera connectivity. These are adjacent IT/device problems, not verified telecom service fixes. Row 245's answer even assumes dual-band router capability without the complaint establishing it.

Updated decision after scope correction: index all 257 as lower-trust `unverified_ticket` evidence. Similar replies may inform an explicitly qualified suggestion, never a confirmed historical fix. A generated synthetic history with explicit outcomes and an expanded KB supplements these records. Nonresolved history cannot supply successful fixes. Telecom Conversation Corpus inspection and provider-policy evidence remain pending. The original nine records remain preserved.

Twenty-five public complaint texts are reserved as query-only evaluation cases, with their original indexed record excluded during evaluation. These are public-language queries of unverified origin, not confirmed real customer data. Manual relevance labels and near-duplicate review remain necessary before reporting quality metrics. Source attribution and licence are retained.

## Reproducible optional public setup

Run `python download_public.py`. It downloads the audited CSV from revision `ddf1c81a5475992c4fa6752bf1e8b4e31f07bbeb`, verifies SHA256 `f187c090e59581c2bbf3aa1377c8db4dd647464ecf2ae51bf8966e42e0ed6bc0`, and runs the existing filter. The [source file page](https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets/blob/ddf1c81a5475992c4fa6752bf1e8b4e31f07bbeb/aa_dataset-tickets-multi-lang-5-2-50-version.csv) exposes the file/hash; dataset attribution and CC-BY-NC-4.0 remain unchanged. Checksum mismatch preserves previous data. Re-running reuses a matching local file. Raw/candidate data stay ignored, and held-out query labels are not regenerated.

## Telecom Conversation Corpus inspection (3 October 2026)

Inspected the [Talkmap dataset card and preview](https://huggingface.co/datasets/talkmap/telecom-conversation-corpus), plus the first 100 rows from the public dataset-server API. The card describes 200,000 synthetic conversations and declares MIT; its viewer reports 3,726,699 utterance rows. Conversations and rows are different units.

The bounded sample has 100 utterances spanning seven conversation IDs: 52 agent and 48 client turns. Columns are conversation_id, speaker, date_time and text, with no explicit resolved-outcome column. Visible dialogue includes mobile reception/dropped-call complaints, attempted restarts, identity/PIN exchanges, escalation and offers of provider-specific concessions. Some utterances contain grammatical artifacts or contradictory statements. A friendly closing or a proposed remedy does not prove it worked.

Decision: suitable for conversation/query/topic scenarios with synthetic-origin labels; unsuitable for automatic import as confirmed resolution history or provider policy. The inspected raw sample remains ignored in scratch storage and is not redistributed. Preserve the existing 257 unverified tickets and explicit synthetic histories; this inspection does not remove any agreed evidence. A future larger conversation adapter should reconstruct turns by conversation ID and separately review outcomes and policy claims.
