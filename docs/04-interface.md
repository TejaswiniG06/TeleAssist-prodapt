# The demo interface

Explain it this way: the page collects a complaint and observations, calls the existing services, and displays the answer with inspectable evidence. Retrieval and grounding decisions stay in Python; the browser renders their results.

Run `.venv/Scripts/python.exe -m uvicorn api:app --host 127.0.0.1 --port 8000`, then open http://127.0.0.1:8000/. FastAPI serves one plain HTML file at `/`. There is no frontend framework, separate build or additional service to defend.

“Find evidence” calls `/search` using the selected keyword, semantic or hybrid mode and optional product filter. “Prepare draft” calls `/resolve` using the complaint and observations. Drafting chooses evidence automatically; the search controls do not silently override its grounding rules.

The page distinguishes a resolution draft, clarification and escalation. Citations show source IDs, versions and evidence tiers. “View evidence” opens the underlying article or historical steps, conditions, outcome and provenance. Unverified public replies and synthetic history remain visibly labelled. Empty results, validation errors, provider fallbacks and loading states are handled explicitly.

The browser inserts returned content with `textContent`, so ticket text is displayed as text rather than executable HTML. It uses same-origin requests, stores no complaints in local storage, and never receives the provider API key. The raw form value stays in browser memory while entered; server-side masking occurs before retrieval/generation. Clear resets the form and displayed output.

This is an agent-review interface. It does not execute suggested actions or send a message to the customer. Keep the server bound to localhost until authentication and access restrictions are implemented. Cleanup remains deferred until the full prototype is complete.
# Verification

All 26 backend regression tests passed after adding the root route. A headless Edge browser checked real keyword search against the 487-record local service, evidence expansion, clear/reset, and desktop/mobile layout. Mocked provider responses checked clarification rendering, literal HTML handling through textContent, and recovery after HTTP 503. No browser script errors occurred. These browser checks verify presentation; they do not measure LLM answer quality. Earlier live resolution checks cover the provider separately.
