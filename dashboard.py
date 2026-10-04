"""Case workspace: presentation only, backed by the FastAPI services."""
import json
from uuid import uuid4
import streamlit as st
from dashboard_client import DashboardClient, DashboardError


TIERS = {'kb':'Knowledge base', 'resolved':'Resolved history',
         'unverified':'Unverified suggestion', 'unresolved':'Unresolved history'}


def text(value):
    # Render untrusted customer/evidence text without interpreting Markdown or HTML.
    st.text(str(value))


def source_view(record):
    st.caption(f"{record['id']} · version {record.get('version', 'unknown')}")
    text(record.get('title', record['id']))
    tier = record.get('evidence_tier', 'unknown')
    label = TIERS.get(tier, tier)
    if tier in ('unverified', 'unresolved'):
        st.warning(label)
    else:
        st.caption(label)
    st.caption('Origin: ' + record.get('provenance', 'unknown'))
    for field in ('complaint', 'applicability', 'outcome', 'outcome_evidence',
                  'suggested_steps', 'escalation', 'creator', 'license', 'source_url'):
        if record.get(field):
            st.caption(field.replace('_', ' ').capitalize())
            text(record[field])
    for field in ('observations', 'symptoms'):
        for value in record.get(field, []):
            text(value)
    for step in record.get('steps', []) + record.get('resolution_steps', []):
        text(step['instruction'])
        st.caption('Condition')
        text(step.get('condition', ''))


def citations(client, items):
    if not items:
        st.caption('No cited resolution steps.')
    for item in items:
        with st.expander(f"{item['id']} · version {item['version']}"):
            # Always inspect the citation's exact version, including retired evidence.
            source_view(client.source(item['id'], item['version']))


def reset_case():
    st.session_state.complaint = ''
    st.session_state.observations = ''
    st.session_state.pop('case_result', None)
    for field in ('case_inputs', 'case_request_id', 'saved_case_id'):
        st.session_state.pop(field, None)


def assistant(client):
    st.title('Complaint workspace')
    st.caption('Prepare an evidence-backed response. Each submission is an independent case.')
    st.button('New complaint', on_click=reset_case)
    entry, review = st.columns([1, 1.3], gap='large')
    with entry:
        with st.form('complaint_form'):
            complaint = st.text_area('Customer complaint', key='complaint', max_chars=5000,
                                     height=160, placeholder='Describe the service and symptoms…')
            observations = st.text_area('Observations and actions already tried',
                                         key='observations', max_chars=3000, height=120)
            query_mode = st.selectbox('Resolution search query', ['enriched','raw'],
                                      help='Enriched reuses this request’s classification; raw preserves the original retrieval behaviour. Neither adds a query-rewriting call.')
            submitted = st.form_submit_button('Prepare response', type='primary')
        st.caption('Common identifiers are masked by the backend. Pattern masking is not comprehensive anonymization.')
        if submitted:
            st.session_state.pop('case_result', None)
            for field in ('case_inputs', 'case_request_id', 'saved_case_id'):
                st.session_state.pop(field, None)
            if not complaint.strip():
                st.error('Enter a complaint first.')
            else:
                with st.spinner('Classifying, retrieving evidence and checking the draft…'):
                    st.session_state.case_result = client.request('/resolve',
                        {'complaint':complaint.strip(), 'observations':observations.strip(), 'query_mode':query_mode})
                    st.session_state.case_inputs = {'complaint':complaint.strip(), 'observations':observations.strip()}
                    st.session_state.case_request_id = uuid4().hex
    with review:
        result = st.session_state.get('case_result')
        if not result:
            st.info('Your response and source evidence will appear here.')
            return
        st.subheader({'resolution':'Resolution draft', 'clarification':'More information needed',
                      'escalation':'Agent review needed'}.get(result['status'], result['status']))
        text(result['answer'])
        if result.get('generation') == 'fallback':
            st.warning('Checked drafting was unavailable: ' + result.get('reason', 'unknown'))
        for question in result.get('questions', []):
            text(question)
        st.caption('Agent review required before applying any proposed action.')
        st.caption('Saving keeps a pending case. A draft is not a confirmed resolution.')
        if st.button('Save pending case', disabled=bool(st.session_state.get('saved_case_id'))):
            payload = {**st.session_state.case_inputs, 'request_id':st.session_state.case_request_id,
                       'draft':{'status':result['status'], 'answer':result['answer'],
                                'classification':result['classification'],
                                'citations':[{'id':item['id'], 'version':item['version']}
                                             for item in result.get('citations', [])]}}
            saved = client.request('/cases', payload, editor=True)
            st.session_state.saved_case_id = saved['id']
        if st.session_state.get('saved_case_id'):
            st.success('Saved: ' + st.session_state.saved_case_id)
            st.caption('Open Saved Cases to record actual actions and the customer outcome. New complaint clears this form, not the saved case.')
        with st.container(border=True):
            st.subheader('Case details')
            classification = result['classification']
            st.table([{'Field':key.capitalize(), 'Suggested value':classification.get(key, 'unknown')}
                      for key in ('product','category','severity','sentiment')])
            if result.get('classification_notice'):
                text(result['classification_notice'])
            if classification.get('churn_risk'):
                st.warning('Explicit cancellation threat detected')
                text(classification.get('churn_evidence', ''))
            else:
                st.caption('No explicit cancellation threat detected.')
            attempts = classification.get('attempted_actions', [])
            if attempts:
                st.caption('Actions already tried')
                st.dataframe(attempts, hide_index=True)
            st.caption('Citation check: ' + result.get('citation_check', 'unknown'))
            st.caption('Search query mode: ' + result.get('query_mode', 'unknown'))
        st.subheader('Cited evidence')
        citations(client, result.get('citations', []))
        with st.expander('Processed complaint and masking counts'):
            text(result['masked_complaint'])
            st.json(result.get('mask_counts', {}))


def saved_cases(client, editor=False):
    st.title('Saved Cases')
    st.caption('Pending drafts stay separate from searchable history. Record what actually happened, then request editor review.')
    st.button('Refresh saved cases')
    listing = client.request('/cases?limit=100', editor=True)
    st.caption(listing['notice'])
    if not listing['cases']:
        st.info('No cases saved yet. Prepare a response and choose Save pending case.')
        return
    st.dataframe(listing['cases'], hide_index=True)
    ids = [item['id'] for item in listing['cases']]
    preferred = st.session_state.get('saved_case_id')
    selected = st.selectbox('Case to inspect', ids, index=ids.index(preferred) if preferred in ids else 0)
    case = client.request('/cases/' + selected, editor=True)
    st.caption(f"{case['id']} · revision {case['revision']} · {case['status']}")
    st.subheader('Saved complaint')
    text(case['complaint'])
    if case['observations']:
        st.caption('Additional observations'); text(case['observations'])
    with st.expander('Original draft — unconfirmed'):
        text(case['draft']['answer'])
        st.json(case['draft']['classification'])
        st.json(case['draft'].get('citations', []))
    if case.get('outcome'):
        st.subheader('Recorded outcome')
        text(case['outcome']['outcome'])
        for action in case['outcome']['actual_actions']:
            text(action)
        text(case['outcome']['outcome_evidence'])
    if case.get('review'):
        st.caption('Editor review'); text(case['review']['rationale'])
    publication = case.get('publication') or {}
    if publication.get('error'):
        st.warning(publication['error'])
    if case['status'] in ('pending', 'outcome_recorded', 'rejected'):
        with st.form('outcome_' + selected):
            outcome = st.selectbox('Actual outcome', ['resolved', 'not_resolved'])
            actions = st.text_area('Actions actually performed — one per line', max_chars=12000,
                help='Enter observed actions, not suggestions copied from the draft. Leave blank if no action was taken and the issue remains unresolved.')
            evidence = st.text_area('How was the outcome confirmed?', max_chars=2000,
                help='Record customer confirmation or observed results. Avoid personal identifiers.')
            confirmed = st.checkbox('I confirm these actions and this outcome were actually reported or observed')
            submit = st.form_submit_button('Record actual outcome')
        if submit:
            if not confirmed:
                st.error('Confirm the actual outcome before saving.')
            else:
                client.request('/cases/' + selected + '/outcome',
                    {'expected_revision':case['revision'], 'outcome':outcome,
                     'actual_actions':[line.strip() for line in actions.splitlines() if line.strip()],
                     'outcome_evidence':evidence.strip(), 'confirmed':True}, editor=True)
                st.rerun()
    if editor and case['status'] == 'outcome_recorded':
        st.subheader('Editor review and publication')
        categories = client.request('/taxonomy', editor=True)['categories']
        version = client.request('/health', editor=True)['index_version']
        st.caption(f'Publication will use index version {version}. Resolved cases become resolved history; unsuccessful cases stay unresolved.')
        with st.form('case_review_' + selected):
            decision = st.selectbox('Review decision', ['approve', 'reject'])
            title = st.text_input('Historical ticket title', max_chars=250)
            product = st.selectbox('Reviewed product', ['broadband', 'mobile', 'fixed_voice', 'iptv'])
            category = st.selectbox('Reviewed category', categories)
            applicability = st.text_area('When do these historical actions apply?', max_chars=1500)
            rationale = st.text_area('Review rationale', max_chars=1000)
            confirmed = st.checkbox('I reviewed the actual actions, outcome, product and applicability')
            submit = st.form_submit_button('Submit case review')
        if submit:
            if not confirmed:
                st.error('Review and confirm before publishing or rejecting.')
            else:
                client.request('/admin/cases/' + selected + '/review',
                    {'expected_revision':case['revision'], 'expected_index_version':version,
                     'decision':decision, 'title':title.strip(), 'product':product, 'category':category,
                     'applicability':applicability.strip(), 'rationale':rationale.strip(), 'confirmed':True}, editor=True)
                st.rerun()
    elif case['status'] == 'outcome_recorded':
        st.info('Outcome saved. An editor must review it before it becomes searchable evidence.')
    if case['status'] == 'publishing':
        st.info('Indexing is in progress. Refresh to check publication; the existing search index remains available.')
    if case['status'] == 'published':
        st.success('Published as historical evidence: ' + case['publication']['source_id'])
        source_view(client.source(case['publication']['source_id'], case['publication']['source_version']))
    with st.expander('Case activity'):
        st.json(case['events'])


def evidence(client):
    st.title('Evidence Explorer')
    st.caption('Search articles and past tickets. Similarity does not prove a fix applies.')
    with st.form('evidence_search'):
        query = st.text_input('Search evidence', max_chars=2000)
        a, b, c = st.columns(3)
        mode = a.selectbox('Search mode', ['hybrid','keyword','semantic'])
        product = b.selectbox('Product', ['All','broadband','mobile','fixed_voice','iptv'])
        kind = c.selectbox('Record type', ['All','article','resolved_ticket','unverified_ticket','unresolved_ticket'])
        submitted = st.form_submit_button('Search', type='primary')
    if submitted:
        st.session_state.pop('search_result', None)
        if not query.strip():
            st.error('Enter a search query.')
        else:
            payload = {'query':query.strip(), 'mode':mode, 'limit':8}
            if product != 'All': payload['product'] = product
            if kind != 'All': payload['record_type'] = kind
            with st.spinner('Searching evidence…'):
                st.session_state.search_result = client.request('/search', payload)
    result = st.session_state.get('search_result')
    if result:
        st.caption(f"{result['mode']} · index version {result['index_version']}")
        if not result['results']: st.info('No matching evidence. Clarify the product and symptoms.')
        for hit in result['results']:
            with st.container(border=True):
                st.caption(f"Ranking score: {hit['score']:.4f}")
                source_view(hit['record'])
    with st.expander('Inspect a source version'):
        with st.form('inspect_source'):
            source_id = st.text_input('Source ID', max_chars=80)
            version = st.number_input('Version (0 means current)', min_value=0, step=1)
            inspect = st.form_submit_button('Inspect')
        if inspect and source_id.strip():
            source_view(client.source(source_id.strip(), int(version) or None))


def knowledge(client):
    st.title('Knowledge & Topics')
    st.caption('Editor actions change shared evidence or taxonomy. Review before submitting.')
    topics = client.request('/admin/topics', editor=True)
    st.caption(f"{topics['buffered_distinct_complaints']} distinct weak-match complaints · storage {topics['storage_state']}")
    st.subheader('Topic proposals')
    if not topics['proposals']: st.info('No topic proposals currently meet the clustering threshold.')
    for proposal in topics['proposals']:
        with st.expander(', '.join(proposal['suggested_terms']) + ' · ' + proposal['status']):
            st.caption(f"{proposal['distinct_complaints']} distinct complaints · {proposal['occurrences']} occurrences")
            for example in proposal['examples']: text(example)
            if proposal['status'] == 'pending':
                with st.form('review_' + proposal['id']):
                    decision = st.selectbox('Decision', ['approve','reject'])
                    category = st.text_input('New category (for approval)', max_chars=80)
                    rationale = st.text_area('Rationale', max_chars=1000)
                    confirm = st.checkbox('I reviewed these examples and the category decision')
                    submit = st.form_submit_button('Submit review')
                if submit:
                    if not confirm or len(rationale.strip()) < 10:
                        st.error('Confirm your review and supply at least 10 characters of rationale.')
                    else:
                        client.request('/admin/topics/' + proposal['id'] + '/review',
                            {'decision':decision,'category':category.strip() if decision=='approve' else '',
                             'rationale':rationale.strip()}, editor=True)
                        st.rerun()
            elif proposal.get('review'): st.json(proposal['review'])
    st.caption(topics['notice'])
    with st.expander('Current taxonomy'):
        st.json(client.request('/taxonomy')['categories'])
    st.subheader('Evidence updates')
    st.caption('Submit an IngestRequest JSON batch with expected index/source versions. Schema is documented at the retrieval API /docs.')
    with st.form('ingestion'):
        batch = st.text_area('Validated evidence batch (JSON)', height=180)
        confirmed = st.checkbox('I reviewed the records, provenance and expected versions')
        submit = st.form_submit_button('Submit indexing job')
    if submit:
        if not confirmed: st.error('Review and confirm the batch first.')
        else:
            try:
                payload = json.loads(batch)
                if not isinstance(payload, dict): raise ValueError()
            except ValueError:
                st.error('Enter a JSON object matching the ingestion schema.')
            else:
                job = client.request('/admin/ingest', payload, editor=True)
                st.session_state.last_job = job['id']
                st.success('Indexing job submitted: ' + job['id'])
    with st.form('job_status'):
        job_id = st.text_input('Job ID', value=st.session_state.get('last_job', ''))
        check = st.form_submit_button('Check job status')
    if check and job_id.strip():
        from urllib.parse import quote
        st.json(client.request('/admin/jobs/' + quote(job_id.strip(), safe=''), editor=True))
    with st.expander('Publication audit'):
        st.json(client.request('/admin/audit', editor=True)['entries'])


def health(client):
    st.title('System Health')
    st.button('Refresh measurements')
    service = client.request('/health')
    a, b, c = st.columns(3)
    a.metric('Active evidence', service['active_sources'])
    b.metric('Index version', service['index_version'])
    c.metric('Semantic state', service['semantic_state'])
    st.caption('Generation configured: ' + str(service['generation_configured']) + ' (configuration does not confirm provider availability)')
    st.json(client.request('/ready'))
    metrics = client.request('/admin/metrics', editor=True)
    st.subheader('Latency by endpoint')
    rows = [{'Endpoint':route, **values} for route, values in metrics['latency_ms'].items()]
    if rows: st.dataframe(rows, hide_index=True)
    else: st.info('No latency samples yet.')
    for field in ('requests','http_errors','resolution_outcomes','fallback_reasons','ingestion_jobs','process'):
        if field in metrics:
            with st.expander(field.replace('_', ' ').capitalize()): st.json(metrics[field])
    st.caption(f"Uptime: {metrics['uptime_seconds']} seconds · in-flight requests: {metrics['inflight']}")
    st.caption(metrics['notice'])


def main():
    st.set_page_config(page_title='TeleAssist · Case workspace', page_icon='📡', layout='wide')
    st.header('TeleAssist', divider='green')
    with st.expander('Application access'):
        st.text_input('Application access key', type='password', key='application_key',
                      help='Agent/editor application key, never the Gemini provider key. Local agent mode can leave this blank.')
        st.caption('Access is verified by the backend. No role picker. Keys remain in this session and are not saved to disk.')
    key = st.session_state.get('application_key', '')
    # Changing identity must not retain case/evidence data from the preceding identity.
    if st.session_state.get('identity', '') != key:
        reset_case()
        for name in ('search_result','last_job'):
            st.session_state.pop(name, None)
        st.session_state.identity = key
    client = DashboardClient(key)
    pages = [st.Page(lambda: assistant(client), title='Support Assistant', url_path='assistant', default=True),
             st.Page(lambda: evidence(client), title='Evidence Explorer', url_path='evidence')]
    try:
        editor = client.request('/admin/access', editor=True).get('role') == 'editor'
    except DashboardError as error:
        editor = False
        if (error.status == 401 and key) or error.status not in (401,403,503):
            st.warning(str(error))
    if editor:
        pages.extend([st.Page(lambda: knowledge(client), title='Knowledge & Topics', url_path='knowledge'),
                      st.Page(lambda: health(client), title='System Health', url_path='health')])
    pages.insert(1, st.Page(lambda: saved_cases(client, editor), title='Saved Cases', url_path='cases'))
    try:
        st.navigation(pages, position='top').run()
    except DashboardError as error:
        st.error(str(error))


if __name__ == '__main__':
    main()
