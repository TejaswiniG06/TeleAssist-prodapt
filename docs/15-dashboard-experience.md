# Dashboard interaction design

This redesign changes presentation only. Existing FastAPI contracts, permission checks, retrieval, resolution, evidence ingestion and case persistence remain unchanged.

## Workspaces and permissions

The landing page offers Support Agent and Knowledge Editor cards. Agents can prepare responses, search evidence and follow up on saved cases. Editors verify their application key through /admin/access before seeing Evidence, Saved Cases, Topics and Health. Role selection is navigation, not authorization; each API operation remains protected by the backend.

Switch role returns to the landing page and clears the application key, form, displayed results and navigation selection. It does not delete persistent cases. Agents can enter a required application key under Advanced access permissions and explicitly choose Apply access key. Changing the applied identity clears the current case to prevent mixing access sessions. The provider key never belongs in the dashboard.

## Complaint entry

Examples live in a collapsed Load an example section and never submit or save automatically. An optional device selector appends device context to observations; Other accepts a short device description. It never overrides the classified service. Selecting an already-tried action adds a readable observation with result unknown; it does not invent a failed outcome. Removing a tag removes only its generated line, preserving other notes. Additional details are optional.

Prepare troubleshooting draft invokes the existing /resolve endpoint. Search supporting sources invokes /search for the current complaint without a classification or drafting request, and shows related sources alongside the form. The dedicated Evidence Explorer retains mode/product/type filters and exact-version inspection. Search approach remains available under Advanced search settings, with raw and enriched values unchanged.

## Waiting and results

The synchronous resolution API does not stream intermediate stage events. The loading panel says Preparing your draft with a simple skeleton; it never invents completed stages. The returned status determines whether the UI presents a draft, clarification or specialist review. Toast messages distinguish a draft from a non-resolution response.

Already-tried actions are highlighted before the response. Each resolution step has an accordion containing its full instruction, tier label, support quote, conditions, matching customer text and exact source version. Supporting sources use Previous/Next cards; controls preserve cited versions, including retired history. Generated/customer/evidence strings render as text; the HTML badge helper escapes labels and allowlists styles.

Clarification responses show one answer field directly beneath each unique question and one Continue button. Repeated question text is removed from the response summary; submitted observations keep each question paired with its answer. This submits the retained original complaint with accumulated observations to the same /resolve endpoint. It does not create chatbot memory, consume a call for empty answers, or save a case automatically. Starting another case clears clarification and device state.

Saving a case remains explicit. It stores an unconfirmed snapshot; actual outcome capture and editor review still precede publication. Case cards distinguish reported outcomes from publication status. Approve and publish / Reject case retain review rationale, confirmation and optimistic versions. New case clears current input rather than operational storage.

## Human-readable editor screens

Open case selects the requested record and opens its details immediately; Back to recent cases restores the cards. Draft classification, citations and case activity use labels/tables. Outcomes and evidence publication still require explicit confirmations. Case deletion remains future work; retiring evidence removes it from current search while preserving cited versions.

Evidence management provides Add, Update and Retire forms for all four evidence kinds. The UI obtains source/index versions when a record is opened; the existing API rejects stale submissions. Step instructions, action names and applicability conditions use matching lines. Source attribution, outcome confirmation and synthetic/unverified origin remain explicit. A collapsed developer batch import preserves the existing multi-record capability. Job state and publication activity use readable statuses/tables.

Topics explains weak-match complaint grouping, renders proposal cards and provides a searchable, collapsed list of existing categories. It does not rename stored categories or change clustering thresholds.

Health shows available sources, search readiness, AI configuration, individual service availability, response times and errors from live APIs. An unavailable service is reported while the surviving service remains visible. Raw readiness/process counters remain in optional Technical details. Configuration is not proof of provider availability, and request counters include dashboard checks.

## Styling and accessibility

A session-level Light/Dark appearance picker changes presentation without changing inputs or permissions. The light theme uses primary #1E46B8, background #F5F7FA, white surfaces, text #17202E and secondary text #4B5668. Evidence/severity/outcome colours always accompany text labels. Role hover effects, card entrances and navigation cues use short transitions; prefers-reduced-motion disables animation/transition. Narrow screens stack columns and controls. Toolbar actions and Deploy are hidden while native navigation remains visible.

Health tiles show actual API values immediately with an entrance transition. They do not count through invented intermediate numbers. Operational health stays separate from frozen evaluation scores.

`dashboard.py` is the Streamlit entry point. `frontend/app.py` owns role choice/navigation; the five `frontend/views/` modules own screen composition and existing API interactions. `frontend/components.py` owns small presentation helpers, example/action choices and source-card navigation. `frontend/styles.css` owns styling, with the Streamlit theme configured in .streamlit/config.toml. Native widget styling selectors should be rechecked after dependency upgrades.

## Verification

The original UI redesign checkpoint passed 83 tests, including the full saved-case/outcome/publication flow against the real API. Five redesign checks cover verified editor login and key persistence, editor authorization, example/switch-role behaviour, unknown action outcomes and exact-version Previous/Next navigation. A real browser checked the configured provider's draft, action chips, source navigation, denial of an invalid editor key, 360px layout and reduced-motion styles, without JavaScript errors.

An isolated browser audit also verified editor login, all four editor screens, topic approval, case publication and evidence addition/retirement through HTTP. It used fictional records and fake embeddings with no provider calls or writes to the live data. The running dashboard was rechecked after restarting Streamlit to clear a stale helper-module import.

The usability update retains both roles and all API contracts. All 93 tests pass. Six additional behavioural checks cover device/clarification continuation and reset, saved-card selection, theme input preservation, add/update/retire forms with stale-version rejection and partial service outages. An isolated real-model browser audit passed light/dark appearance, 360px layout, clarification, masking, saving/opening cases, evidence addition/retirement, historical citations, Topics and both service health panels, with zero JavaScript errors and no provider calls. A separate live provider request returned a valid clarification with attempted-action information, no fallback and no saved test case. The real HTTP microservice smoke check also passed.

Follow-up verification: all 93 tests pass. A browser fixture verified individual question fields, deduplication and paired-answer submission without provider calls. Real dashboard checks measured selected/unselected action pills and narrow-screen navigation contrast in both themes: all checked ratios exceed 4.5:1, with zero JavaScript errors. Native buttons use data-variant selectors; the navigation drawer uses themed surfaces and link colours.
