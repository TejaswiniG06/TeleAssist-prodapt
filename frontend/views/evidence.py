"""Evidence search and form-based, version-checked publishing through the existing API."""
from urllib.parse import quote
from uuid import uuid4
import json
import streamlit as st
from frontend.components import source_view, search_hit_view, carousel, text

PRODUCTS = ['broadband', 'mobile', 'fixed_voice', 'iptv', 'unknown']
KINDS = ['article', 'resolved_ticket', 'unresolved_ticket', 'unverified_ticket']
KIND_NAMES = dict(zip(KINDS, ['Knowledge-base article', 'Resolved ticket', 'Unresolved ticket', 'Unverified public ticket']))
ORIGINS = ['reviewed_internal', 'synthetic_demo', 'synthetic_llm', 'public_origin_unverified']
ORIGIN_NAMES = dict(zip(ORIGINS, ['Reviewed internal evidence', 'Synthetic demonstration', 'Synthetic AI-generated evidence', 'Public source — outcome unverified']))


def evidence(client):
    st.title('Evidence Explorer')
    st.caption('Search guidance and past tickets, including approved saved cases. Check whether a source applies before using it.')
    with st.form('evidence_search'):
        query = st.text_input('Search evidence', max_chars=2000, placeholder='For example: broadband disconnects every evening')
        a, b, c = st.columns(3)
        mode = a.selectbox('Search mode', ['hybrid','keyword','semantic'], format_func=lambda value:{'hybrid':'Words + meaning', 'keyword':'Matching words', 'semantic':'Similar meaning'}[value])
        product = b.selectbox('Product', ['All', *PRODUCTS[:-1]], format_func=lambda value:value.replace('_', ' ').capitalize())
        kind = c.selectbox('Record type', ['All', *KINDS], format_func=lambda value:KIND_NAMES.get(value, value))
        submitted = st.form_submit_button('Search', type='primary')
    if submitted:
        st.session_state.search_result_mode = mode
        st.session_state.pop('search_result', None)
        if not query.strip(): st.error('Enter a search query.')
        else:
            payload = {'query':query.strip(), 'mode':mode, 'limit':8}
            if product != 'All': payload['product'] = product
            if kind != 'All': payload['record_type'] = kind
            with st.spinner('Searching evidence…'):
                st.session_state.search_result = client.request('/search', payload)
    result = st.session_state.get('search_result')
    if result:
        if not result['results']: st.info('No matching evidence. Try describing the product and symptoms.')
        carousel(result['results'], 'search_sources',
                 lambda hit:search_hit_view(hit, st.session_state.get('search_result_mode', 'hybrid')),
                 label='Relevance rank')
    with st.expander('Open a source by ID'):
        st.caption('Copy an ID from a source card, such as KB-003. This opens a specific record, not a complaint search. Version 0 opens the latest; another number opens that saved version.')
        with st.form('inspect_source'):
            source_id = st.text_input('Source reference', max_chars=80, placeholder='For example: KB-003', help='Enter the source ID, not a product name such as broadband.')
            version = st.number_input('Source version (0 means latest)', min_value=0, step=1)
            inspect = st.form_submit_button('View source')
        if inspect and source_id.strip(): source_view(client.source(source_id.strip(), int(version) or None))


def lines(value):
    return [line.strip() for line in value.splitlines() if line.strip()]


def submit_update(client, payload):
    job = client.request('/admin/ingest', payload, editor=True)
    st.session_state.last_job = job['id']
    st.success('Update submitted. Check its status below; search keeps working while it is prepared.')


def evidence_updates(client):
    st.subheader('Manage evidence')
    st.caption('Add guidance, revise a source, or remove it from current search. Earlier cited versions are preserved.')
    operation = st.radio('What would you like to do?', ['Add', 'Update', 'Retire'], horizontal=True, key='evidence_operation')
    stored = st.session_state.get('editing_source')
    if not stored or stored['operation'] != operation:
        st.session_state.pop('editing_source', None)
        stored = None
    if operation == 'Add' and stored is None:
        if st.button('Start new evidence record'):
            st.session_state.editing_source = {'operation':operation, 'index_version':client.request('/health', editor=True)['index_version'],
                'version':0, 'record':{'id':'KB-' + uuid4().hex[:12], 'record_type':'article'}, 'token':uuid4().hex}
            st.rerun()
    elif operation != 'Add':
        with st.form('load_edit_source'):
            source_id = st.text_input('Source reference to ' + operation.lower(), max_chars=80, placeholder='Copy the reference from an evidence card')
            load = st.form_submit_button('Load source')
        if load and source_id.strip():
            index_version = client.request('/health', editor=True)['index_version']
            record = client.source(source_id.strip())
            st.session_state.editing_source = {'operation':operation, 'index_version':index_version,
                'version':record['version'], 'record':record, 'token':uuid4().hex}
            st.rerun()
    if stored:
        record_form(client, stored)
    with st.expander('Check an evidence update', expanded=bool(st.session_state.get('last_job'))):
        with st.form('job_status'):
            job_id = st.text_input('Update reference', value=st.session_state.get('last_job', ''))
            check = st.form_submit_button('Check update status')
        if check and job_id.strip():
            job = client.request('/admin/jobs/' + quote(job_id.strip(), safe=''), editor=True)
            if job['status'] == 'published': st.success('Published — the updated evidence is now available in search.')
            elif job['status'] == 'failed': st.error(job.get('error', 'Update failed. Previous evidence remains available.'))
            else: st.info('Update is ' + job['status'] + '. Check again shortly.')
    with st.expander('Publication activity'):
        entries = client.request('/admin/audit', editor=True)['entries']
        if entries:
            st.table([{'Time (UTC)':item.get('at', ''), 'Search revision':item.get('index_version', ''),
                       'Changed sources':', '.join(source['id'] for source in item.get('sources', [])), 'Published by':item.get('role', '')} for item in entries])
        else: st.caption('No evidence updates have been published yet.')
    # Keep the existing batch capability for developers without requiring JSON from editors.
    with st.expander('Advanced batch import — for developers'):
        st.caption('Import multiple reviewed records using JSON. For normal editing, use Add, Update or Retire above.')
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
                except ValueError: st.error('Enter a JSON object matching the ingestion schema.')
                else: submit_update(client, payload)


def record_form(client, stored):
    old = stored['record']
    token = stored['token']
    operation = stored['operation']
    st.caption('Source reference: ' + old['id'])
    if operation == 'Retire':
        source_view(old)
        with st.form('retire_' + token):
            confirmed = st.checkbox('Remove this source from current search; retain its citation history')
            submit = st.form_submit_button('Retire source', type='primary')
        if submit:
            if not confirmed: st.error('Confirm retirement before submitting.')
            else:
                fields = ('id','title','record_type','product','category','status','provenance','complaint','observations','symptoms','steps','resolution_steps','suggested_steps','outcome','outcome_evidence','applicability','escalation','source_url','creator','license')
                record = {key:value for key, value in old.items() if key in fields}
                record['status'] = 'retired'
                submit_update(client, {'expected_index_version':stored['index_version'], 'changes':[{'expected_version':stored['version'], 'record':record}]})
        return
    kind = st.selectbox('Evidence kind', KINDS, index=KINDS.index(old.get('record_type', 'article')), format_func=lambda value:KIND_NAMES[value], key='edit_kind_' + token)
    with st.form('edit_record_' + token + kind):
        title = st.text_input('Title', value=old.get('title', ''), max_chars=250)
        product = st.selectbox('Affected service', PRODUCTS, index=PRODUCTS.index(old.get('product', 'broadband')), format_func=lambda value:value.replace('_', ' ').capitalize())
        category = st.text_input('Issue category', value=old.get('category', ''), max_chars=80, help='For example: slow speed. Spaces become underscores.')
        origin = st.selectbox('Where does this evidence come from?', ORIGINS, index=ORIGINS.index(old.get('provenance', 'reviewed_internal')), format_func=lambda value:ORIGIN_NAMES[value])
        applicability = st.text_area('When does this guidance apply?', value=old.get('applicability', ''), max_chars=2000)
        complaint = st.text_area('Original complaint', value=old.get('complaint', ''), max_chars=5000) if kind != 'article' else ''
        observations = st.text_area('Supporting observations — one per line', value='\n'.join(old.get('observations', [])), max_chars=12000)
        symptoms = st.text_area('Symptoms — one per line', value='\n'.join(old.get('symptoms', [])), max_chars=12000)
        actions = old.get('steps' if kind == 'article' else 'resolution_steps', [])
        instructions = conditions = names = ''
        if kind != 'unverified_ticket':
            st.caption('Enter up to 20 steps. Each step needs a matching action name and condition on the same line number.')
            instructions = st.text_area('Steps — one per line', value='\n'.join(a['instruction'] for a in actions), max_chars=30000)
            names = st.text_area('Action names — one per line', value='\n'.join(a['action_id'] for a in actions), help='Use names such as restart_router or check_cables. Preserve existing names when updating.', max_chars=2000)
            conditions = st.text_area('When to use each step — one per line', value='\n'.join(a['condition'] for a in actions), max_chars=30000)
        suggestions = st.text_area('Suggested actions (outcome unverified)', value=old.get('suggested_steps', ''), max_chars=5000) if kind == 'unverified_ticket' else ''
        outcome_evidence = st.text_area('What confirms the actual outcome?', value=old.get('outcome_evidence', ''), max_chars=2000) if kind in ('resolved_ticket','unresolved_ticket') else ''
        escalation = st.text_area('When should a specialist take over? — optional', value=old.get('escalation', ''), max_chars=2000)
        source_url = st.text_input('Original source link — optional for internal evidence', value=old.get('source_url', ''), max_chars=1000)
        creator = st.text_input('Author or source owner', value=old.get('creator', ''), max_chars=250)
        license_name = st.text_input('Licence or usage permission', value=old.get('license', ''), max_chars=100)
        confirmed = st.checkbox('I checked this content, its origin and any reported outcome')
        submit = st.form_submit_button('Publish evidence update', type='primary')
    if submit:
        action_lines, condition_lines, name_lines = lines(instructions), lines(conditions), lines(names)
        if not confirmed: st.error('Review and confirm the content before publishing.')
        elif len(action_lines) != len(condition_lines) or len(action_lines) != len(name_lines):
            st.error('Each step needs one action name and one condition. Keep the line counts equal.')
        else:
            actions = [{'action_id':name.lower().replace(' ', '_'), 'instruction':instruction, 'condition':condition}
                       for name, instruction, condition in zip(name_lines, action_lines, condition_lines)]
            record = {'id':old['id'], 'title':title.strip(), 'record_type':kind, 'product':product,
                'category':category.strip().lower().replace(' ', '_'), 'status':old.get('status', 'active'), 'provenance':origin,
                'applicability':applicability.strip(), 'complaint':complaint.strip(), 'observations':lines(observations), 'symptoms':lines(symptoms),
                'steps':actions if kind == 'article' else [], 'resolution_steps':actions if kind in ('resolved_ticket','unresolved_ticket') else [],
                'suggested_steps':suggestions.strip(), 'outcome':{'resolved_ticket':'resolved','unresolved_ticket':'not_resolved'}.get(kind, 'unknown'),
                'outcome_evidence':outcome_evidence.strip(), 'escalation':escalation.strip(), 'source_url':source_url.strip(),
                'creator':creator.strip(), 'license':license_name.strip()}
            submit_update(client, {'expected_index_version':stored['index_version'], 'changes':[{'expected_version':stored['version'], 'record':record}]})


def editor_evidence(client):
    evidence(client)
    with st.expander('Add, update or retire evidence'):
        evidence_updates(client)
