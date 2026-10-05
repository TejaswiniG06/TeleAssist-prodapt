"""Topics workspace view; backend decisions remain behind HTTP."""
import streamlit as st
from frontend.components import text, badge


def topics_view(client):
    st.title('Emerging topics')
    st.caption('Spot recurring issues that our current knowledge may not cover. Review a group before adding a new issue category.')
    topics = client.request('/admin/topics', editor=True)
    st.metric('Complaints needing better evidence', topics['buffered_distinct_complaints'])
    if topics['storage_state'] != 'ok': st.warning('Topic storage needs attention: ' + topics['storage_state'])
    st.subheader('Topic proposals')
    if not topics['proposals']: st.info('No topic proposals yet. A proposal appears when enough different complaints share similar wording.')
    for proposal in topics['proposals']:
        with st.container(border=True):
            st.subheader(', '.join(proposal['suggested_terms']))
            badge(proposal['status'].capitalize(), 'pending' if proposal['status'] == 'pending' else 'unresolved')
            st.caption(f"{proposal['distinct_complaints']} distinct complaints · {proposal['occurrences']} occurrences")
            for example in proposal['examples']: text(example)
            if proposal['status'] == 'pending':
                with st.form('review_' + proposal['id']):
                    decision = st.selectbox('Decision', ['approve','reject'], format_func=lambda value:'Add a category' if value == 'approve' else 'Dismiss this proposal')
                    category = st.text_input('New category name (for approval)', max_chars=80, help='Use a short name such as evening_outage. Spaces are converted to underscores.')
                    rationale = st.text_area('Why are you making this decision?', max_chars=1000)
                    confirm = st.checkbox('I reviewed these examples and the category decision')
                    submit = st.form_submit_button('Submit review')
                if submit:
                    if not confirm or len(rationale.strip()) < 10:
                        st.error('Confirm your review and supply at least 10 characters of rationale.')
                    else:
                        client.request('/admin/topics/' + proposal['id'] + '/review',
                            {'decision':decision,'category':category.strip().lower().replace(' ', '_') if decision=='approve' else '',
                             'rationale':rationale.strip()}, editor=True)
                        st.rerun()
            elif proposal.get('review'):
                for field, value in proposal['review'].items():
                    st.caption(field.replace('_', ' ').capitalize()); text(value)
    st.caption('Similar wording is a review signal, not proof of a new fault. Approving a category does not create a troubleshooting fix.')
    with st.expander('Browse existing issue categories'):
        categories = client.request('/taxonomy')['categories']
        query = st.text_input('Filter categories', placeholder='For example: mobile or speed')
        visible = [label for label in categories if query.lower() in label.lower().replace('_', ' ')]
        st.caption(f'{len(visible)} of {len(categories)} categories')
        if visible: st.table([{'Category':label.replace('_', ' ')} for label in visible])
        else: st.info('No categories match your filter.')
