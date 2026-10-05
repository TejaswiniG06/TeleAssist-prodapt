"""Readable service health with optional diagnostics; all values come from the API."""
import streamlit as st
from frontend.client import DashboardError


def health(client):
    st.title('System Health')
    st.caption('Check whether search and drafting are available. Measurements reset when a service restarts.')
    st.button('Refresh measurements')
    readings = {}
    targets = [('Retrieval and evidence', True), ('Resolution', False)] if client.url != client.editor_url else [('Combined service', True)]
    for name, editor in targets:
        try:
            readings[name] = {'health':client.request('/health', editor=editor),
                              'ready':client.request('/ready', editor=editor),
                              'metrics':client.request('/admin/metrics', editor=editor)}
        except DashboardError as error:
            st.error(name + ' is unavailable: ' + str(error))
    if not readings: return
    evidence = next(iter(readings.values()))['health']
    tiles = st.columns(3)
    tiles[0].metric('Searchable sources', evidence.get('active_sources', 'Unavailable'))
    tiles[1].metric('Meaning-based search', 'Ready' if evidence.get('semantic_state') == 'ready' else evidence.get('semantic_state', 'Unavailable').capitalize())
    resolution = readings.get('Resolution', next(iter(readings.values())))['health']
    tiles[2].metric('AI settings', 'Configured' if resolution.get('generation_configured') else 'Missing')
    st.caption('Configured AI settings do not confirm provider availability or remaining quota. Those are checked when preparing a draft.')
    for name, reading in readings.items():
        with st.container(border=True):
            st.subheader(name)
            if reading['ready'].get('status') == 'ready': st.success('Service available')
            else: st.warning('Service needs attention: ' + str(reading['ready'].get('status', 'unknown')))
            show_metrics(reading['metrics'])
            with st.expander('Technical details'):
                st.caption('Readiness, index revisions and process diagnostics for debugging.')
                st.json(reading)


def show_metrics(metrics):
    useful = [(route, values) for route, values in metrics.get('latency_ms', {}).items() if route in ('/resolve', '/search')]
    columns = st.columns(2)
    columns[0].metric('Requests with errors', sum(metrics.get('http_errors', {}).values()))
    columns[1].metric('Requests being processed', metrics.get('inflight', 0))
    if useful:
        st.table([{'Task':'Prepare draft' if route == '/resolve' else 'Search evidence',
                   'Typical response (seconds)':round(values['p50']/1000, 2),
                   '95% within (seconds)':round(values['p95']/1000, 2)} for route, values in useful])
    else: st.caption('Response times appear after search or draft requests.')
    outcomes = metrics.get('resolution_outcomes', {})
    if outcomes:
        st.caption('Responses prepared')
        st.table([{'Response':key.replace('_', ' ').capitalize(), 'Count':count} for key, count in outcomes.items()])
    fallbacks = metrics.get('fallback_reasons', {})
    if fallbacks:
        total = sum(fallbacks.values())
        st.warning(f'{total} request(s) since startup returned a safe fallback. This is historical activity, not a live AI availability check.')
        labels = {'grounding_validation_failed':'Response did not pass validation',
                  'provider_unavailable':'AI provider unavailable or quota reached',
                  'generation_not_configured':'AI settings missing',
                  'no_applicable_evidence':'No applicable evidence found',
                  'no_safe_applicable_steps':'No suitable untried steps found'}
        st.table([{'Reason':labels.get(key, key.replace('_', ' ')), 'Count':count} for key, count in fallbacks.items()])
    jobs = metrics.get('ingestion_jobs', {})
    if jobs:
        st.caption('Evidence updates')
        st.table([{'Update status':key.capitalize(), 'Count':count} for key, count in jobs.items()])
    st.caption('Statistics reset when this service restarts. Response times use up to 256 recent requests per task. Counts include dashboard checks. Monitoring does not store complaint text.')
