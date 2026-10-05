"""Cases workspace view; backend decisions remain behind HTTP."""
import re
import streamlit as st
from frontend.components import text, source_view, badge, select_saved_case, classification_view


def saved_cases(client, editor=False):
    st.title('Saved Cases')
    st.caption('Record what happened after troubleshooting. An editor reviews the outcome before it enters shared history.')
    st.button('Refresh saved cases')
    listing = client.request('/cases?limit=100', editor=True)
    if not listing['cases']:
        st.info('No cases saved yet. Prepare a response and choose Save case for follow-up.')
        return
    opened = st.session_state.get('case_details_open', False)
    if opened and st.button('← Back to recent cases'):
        st.session_state.case_details_open = False
        st.rerun()
    if not opened: st.caption('Open a card to view the complaint and record its outcome.')
    cards = st.columns(2) if not opened else []
    for number, item in enumerate(listing['cases'][:5] if not opened else []):
        with cards[number % 2], st.container(border=True, key='casecard_' + item['id']):
            detail = client.request('/cases/' + item['id'], editor=True)
            reported = detail.get('outcome')
            if reported:
                resolved = reported['outcome'] == 'resolved'
                badge('Reported resolved' if resolved else 'Reported not resolved', 'resolved' if resolved else 'unresolved')
            badge({'pending':'Pending outcome', 'outcome_recorded':'Awaiting review', 'publishing':'Publishing',
                   'published':'Published history', 'rejected':'Review rejected'}.get(item['status'], item['status']),
                  'pending' if item['status'] in ('pending','outcome_recorded','publishing') else 'unresolved')
            text(item['complaint']); st.caption(item['id'])
            st.button('Open case', key='open_' + item['id'], on_click=select_saved_case, args=(item['id'],))
    ids = [item['id'] for item in listing['cases']]
    preferred = st.session_state.get('saved_case_id')
    if st.session_state.get('selected_saved_case') not in ids:
        st.session_state.selected_saved_case = preferred if preferred in ids else ids[0]
    if st.session_state.get('case_picker') not in ids:
        st.session_state.case_picker = st.session_state.selected_saved_case
    labels = {item['id']:item['complaint'][:70] + ' · ' + item['id'][-8:] for item in listing['cases']}
    selected = st.selectbox('Choose a saved case', ids, key='case_picker', format_func=lambda value:labels[value])
    st.session_state.selected_saved_case = selected
    case = client.request('/cases/' + selected, editor=True)
    st.caption('Case reference: ' + case['id'])
    st.subheader('Saved complaint')
    text(case['complaint'])
    if case['observations']:
        st.caption('Additional observations'); text(case['observations'])
    with st.expander('Original draft — unconfirmed'):
        text(case['draft']['answer'])
        classification_view(case['draft']['classification'])
        citations = case['draft'].get('citations', [])
        if citations: st.table([{'Source':item['id'], 'Version':item['version']} for item in citations])
        else: st.caption('No sources were cited in this draft.')
    if case.get('outcome'):
        st.subheader('Recorded outcome')
        badge('Resolved' if case['outcome']['outcome'] == 'resolved' else 'Not resolved', 'resolved' if case['outcome']['outcome'] == 'resolved' else 'unresolved')
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
            st.caption('Leave the case pending if the customer has not confirmed an outcome. Submit only actual actions and results.')
            outcome = st.selectbox('Actual outcome', ['resolved', 'not_resolved'], format_func=lambda value: 'Resolved' if value == 'resolved' else 'Not resolved')
            actions = st.text_area('Actions actually performed — one per line', max_chars=12000,
                help='Enter observed actions, not suggestions copied from the draft. Leave blank if no action was taken and the issue remains unresolved.')
            evidence = st.text_area('What confirms whether the issue was fixed?', max_chars=2000,
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
        # Older evidence can retain human-readable labels; new records require category IDs.
        categories = [label for label in categories if re.fullmatch(r'[a-z][a-z0-9_]{0,79}', label)]
        current_category = case['draft']['classification'].get('category', 'unknown')
        selected_category = categories.index(current_category) if current_category in categories else categories.index('unknown')
        version = client.request('/health', editor=True)['index_version']
        st.caption(f'Publication will use index version {version}. Resolved cases become resolved history; unsuccessful cases stay unresolved.')
        with st.form('case_review_' + selected):
            title = st.text_input('Historical ticket title', max_chars=250)
            product = st.selectbox('Reviewed product', ['broadband', 'mobile', 'fixed_voice', 'iptv'])
            category = st.selectbox('Reviewed category', categories, index=selected_category)
            applicability = st.text_area('When do these historical actions apply?', max_chars=1500)
            rationale = st.text_area('Review rationale', max_chars=1000)
            confirmed = st.checkbox('I reviewed the actual actions, outcome, product and applicability')
            approve = st.form_submit_button('Approve and publish', type='primary')
            reject = st.form_submit_button('Reject case')
            submit = approve or reject
            decision = 'approve' if approve else 'reject'
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
        with st.expander('Published historical record'):
            source_view(client.source(case['publication']['source_id'], case['publication']['source_version']))
    with st.expander('Case activity'):
        st.table([{'Activity':event['event'].replace('_', ' ').capitalize(),
                   'Recorded by':event['role'].replace('_', ' '), 'Time (UTC)':event['at']}
                  for event in case['events']])
