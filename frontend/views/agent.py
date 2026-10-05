"""Agent workspace view; backend decisions remain behind HTTP."""
from uuid import uuid4
import streamlit as st
from frontend.components import text, source_card, search_hit_view, badge, tier_badge, carousel, EXAMPLES, ACTION_TAGS, update_tags, WAITING


def reset_case():
    st.session_state.complaint = ''
    st.session_state.observations = ''
    st.session_state.pop('case_result', None)
    for field in ('case_inputs', 'case_request_id', 'saved_case_id', 'tried_tags', 'tag_lines', 'quick_evidence', 'device', 'other_device'):
        st.session_state.pop(field, None)
    for field in list(st.session_state):
        if field.startswith('clarification_'): st.session_state.pop(field, None)


def fill_example(name):
    reset_case()
    st.session_state.complaint = EXAMPLES[name]


def prepare_response(client, complaint, observations, query_mode, panel):
    waiting = panel.empty()
    waiting.markdown(WAITING, unsafe_allow_html=True)
    try:
        result = client.request('/resolve', {'complaint':complaint, 'observations':observations, 'query_mode':query_mode})
        st.session_state.case_result = result
        st.session_state.case_inputs = {'complaint':complaint, 'observations':observations}
        st.session_state.case_request_id = uuid4().hex
        st.session_state.pop('saved_case_id', None)
        st.toast('Suggested resolution ready' if result['status'] == 'resolution' else 'Response ready — more information or review needed')
    finally:
        waiting.empty()


def assistant(client):
    st.title('Let’s work through the complaint')
    st.caption('Describe the issue. We’ll help you prepare a response backed by evidence.')
    st.button('Start another case', on_click=reset_case)
    entry, review = st.columns([1, 1.25], gap='large')
    with entry:
        with st.container(border=True, key='complaint_entry'):
            st.subheader('What is happening?')
            with st.expander('Load an example — optional'):
                st.caption('Fills the form without sending a request.')
                for name in EXAMPLES:
                    st.button(name, on_click=fill_example, args=(name,), use_container_width=True)
            complaint = st.text_area('What problem is the customer facing?', key='complaint', max_chars=5000,
                height=160, placeholder='For example: Our broadband disconnects every evening. Restarting the router did not help.')
            if complaint.strip() and len(complaint.strip()) < 20:
                st.caption('A little more detail helps. Which service is affected, and what happens? You can still submit.')
            device = st.selectbox('Device involved — optional', ['Not sure', 'Router', 'Fiber modem / ONT', 'Mobile phone', 'TV / set-top box', 'Other'], key='device')
            other_device = st.text_input('Which device?', key='other_device', max_chars=150) if device == 'Other' else ''
            st.pills('Fixes already tried', list(ACTION_TAGS), selection_mode='multi',
                     key='tried_tags', on_change=update_tags)
            st.caption('Select fixes actually tried. Tell us below whether they helped.')
            observations = st.text_area('Additional details and fixes already tried — optional',
                key='observations', max_chars=3000, height=120,
                placeholder='Leave blank if unsure. Add affected devices, indicator lights or the results of fixes already tried.')
            with st.expander('Advanced search settings'):
                query_mode = st.selectbox('Search approach', ['enriched','raw'],
                    format_func=lambda value: {'enriched':'Use complaint plus extracted technical terms', 'raw':'Use original complaint wording'}[value],
                    help='Both use the same search engine. Extracted terms can help casual wording, but may also distract ranking.')
            primary, secondary = st.columns(2)
            submitted = primary.button('Prepare troubleshooting draft', type='primary', use_container_width=True)
            find = secondary.button('Search supporting sources', use_container_width=True)
            st.caption('Common identifiers are masked by the backend. Avoid unnecessary personal information; masking is limited.')
        if find:
            if not complaint.strip():
                st.info('Enter a complaint to find related evidence.')
            else:
                st.session_state.quick_evidence = client.request('/search',
                    {'query':complaint.strip()[:2000], 'mode':'hybrid', 'limit':8})
        if st.session_state.get('quick_evidence'):
            with st.expander('Related evidence', expanded=not bool(st.session_state.get('case_result')) and not submitted):
                carousel(st.session_state.quick_evidence['results'], 'quick_sources',
                         lambda hit:search_hit_view(hit, 'hybrid'), label='Relevance rank')
        if submitted:
            for field in ('case_result', 'case_inputs', 'case_request_id', 'saved_case_id'):
                st.session_state.pop(field, None)
            if not complaint.strip():
                st.error('Please describe the customer’s problem first.')
            else:
                device_text = other_device.strip() if device == 'Other' else device if device != 'Not sure' else ''
                combined = '\n'.join(part for part in (observations.strip(), 'Device involved: ' + device_text if device_text else '') if part)
                if len(combined) > 3000:
                    st.error('Please shorten the additional details to leave room for the device information.')
                else:
                    prepare_response(client, complaint.strip(), combined, query_mode, review)
    with review:
        result = st.session_state.get('case_result')
        if not result:
            with st.container(border=True):
                st.subheader('Your response will appear here')
                st.caption('We’ll show the suggested response, actions already tried and supporting evidence. Each case is independent.')
            return
        classification = result['classification']
        attempts = classification.get('attempted_actions', [])
        if attempts:
            st.info('Previously tried')
            for action in attempts:
                text(action.get('action_id', '').replace('_', ' ') + ' · ' + action.get('outcome', 'unknown'))
        with st.container(border=True, key='response_panel'):
            st.subheader({'resolution':'Suggested resolution', 'clarification':'A few details are needed',
                          'escalation':'A support specialist should review this'}.get(result['status'], result['status']))
            questions = list(dict.fromkeys(q.strip() for q in result.get('questions', []) if q.strip()))
            answer = result['answer']
            if result['status'] == 'clarification' and questions:
                for question in questions:
                    answer = answer.replace(question, '')
                answer = ' '.join(answer.split())
            if answer and not result.get('steps'): text(answer)
            for number, step in enumerate(result.get('steps', []), 1):
                text(f"{number}. {step['instruction']}")
                tier_badge(step.get('evidence_tier', 'unknown'))
                st.caption(f"Source: {step['source_id']} · version {step['source_version']}")
                with st.expander(f'Why step {number} was suggested'):
                    st.caption('Supporting quote'); text(step.get('support_quote', ''))
                    st.caption('When this applies'); text(step.get('condition', ''))
                    st.caption('Customer information used'); text(step.get('applicability_evidence', ''))
            if result.get('generation') == 'fallback':
                st.warning('A supported resolution could not be prepared. More details or specialist review may be needed.')
            if result['status'] != 'clarification':
                for question in questions: text(question)
            if result.get('steps'): st.caption('Check that each step applies to the customer’s situation.')
        if result['status'] == 'clarification':
            with st.form('clarification_' + st.session_state.case_request_id):
                st.caption('Answer each question below. Leave an answer blank if you do not know; your original complaint is kept.')
                replies = []
                for number, question in enumerate(questions or ['Answer the clarification questions']):
                    answer = st.text_area(question, max_chars=3000, height=90,
                        placeholder='Type your answer here, or say that you are not sure.',
                        key=f'clarification_answer_{st.session_state.case_request_id}_{number}')
                    if answer.strip():
                        replies.append(f'{question}\nAnswer: {answer.strip()}' if questions else answer.strip())
                answers = '\n'.join(replies)
                continued = st.form_submit_button('Continue', type='primary')
            if continued:
                inputs = st.session_state.case_inputs
                combined = '\n'.join(part for part in (inputs['observations'], answers.strip()) if part)
                if not answers.strip():
                    st.error('Please answer the questions before continuing.')
                elif len(combined) > 3000:
                    st.error('Please shorten your answers. Combined additional details must fit within 3,000 characters.')
                else:
                    prepare_response(client, inputs['complaint'], combined, result.get('query_mode', query_mode), review)
                    st.rerun()
        if st.button('Save case for follow-up', disabled=bool(st.session_state.get('saved_case_id')), type='primary'):
            payload = {**st.session_state.case_inputs, 'request_id':st.session_state.case_request_id,
                       'draft':{'status':result['status'], 'answer':result['answer'],
                                'classification':classification,
                                'citations':[{'id':item['id'], 'version':item['version']} for item in result.get('citations', [])]}}
            saved = client.request('/cases', payload, editor=True)
            st.session_state.saved_case_id = saved['id']
            st.toast('Case saved for follow-up')
        st.caption('Save to follow up. Only confirmed outcomes reviewed by an editor enter shared history.')
        if st.session_state.get('saved_case_id'):
            st.success('Saved: ' + st.session_state.saved_case_id)
            st.caption('Open Saved Cases to record what actually happened. Starting another case does not delete this one.')
        with st.expander('Classification and checks'):
            st.table([{'Field':key.capitalize(), 'Suggested value':classification.get(key, 'unknown')}
                      for key in ('product','category','severity','sentiment')])
            if classification.get('severity') in ('high', 'critical'):
                badge('Suggested severity: ' + classification['severity'], 'high')
            if result.get('classification_notice'): text(result['classification_notice'])
            if classification.get('churn_risk'):
                st.warning('Explicit cancellation threat detected'); text(classification.get('churn_evidence', ''))
            else:
                st.caption('No explicit cancellation threat detected.')
            if attempts: st.dataframe(attempts, hide_index=True)
            st.caption('Citation check: ' + result.get('citation_check', 'unknown'))
            st.caption('Search approach: ' + result.get('query_mode', 'unknown'))
            if attempts:
                for action in attempts: text(action.get('evidence', ''))
            if result.get('reason'): st.caption('Response reason: ' + result['reason'])
        if result.get('citations'):
            with st.expander('Cited sources'):
                carousel(result['citations'], 'citation_sources',
                         lambda item: source_card(client.source(item['id'], item['version'])))
        with st.expander('Processed complaint and masking counts'):
            text(result['masked_complaint'])
            counts = result.get('mask_counts', {})
            if counts: st.table([{'Identifier':key.replace('_', ' '), 'Masked':value} for key, value in counts.items()])
            else: st.caption('No supported identifiers were detected.')
