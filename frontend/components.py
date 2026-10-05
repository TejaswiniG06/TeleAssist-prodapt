"""Presentation helpers only: safe badges, demo inputs and evidence navigation."""
from html import escape
from pathlib import Path
import streamlit as st


EXAMPLES = {
    'Already tried a fix':'My broadband drops every evening. I already restarted the router twice and it did not help.',
    'Casual wording':'net keeps dying at nite, already switched the box off and on, still the same',
    'Not sure what is wrong':'internet not working properly',
}
ACTION_TAGS = {
    'Restarted router':'I restarted the router; result unknown.',
    'Checked cables':'I checked the cables; result unknown.',
    'Airplane mode':'I turned airplane mode on and off; result unknown.',
    'Restarted phone':'I restarted my phone; result unknown.',
}
TIER_LABELS = {'kb':'Knowledge base', 'resolved':'Resolved history',
               'unverified':'Unverified suggestion', 'unresolved':'Unresolved history'}


def apply_style():
    dark = st.session_state.get('appearance', 'Light') == 'Dark'
    palette = ('--primary:#8DAAFF;--ink:#E8EDF7;--muted:#B0BCD0;--surface:#182338;'
               '--background:#101827;--border:#35445C;--input:#202E45;--accent:#243A57;color-scheme:dark;') if dark else (
               '--primary:#1E46B8;--ink:#17202E;--muted:#4B5668;--surface:#FFFFFF;'
               '--background:#F5F7FA;--border:#CAD2E0;--input:#FFFFFF;--accent:#EDF2FF;color-scheme:light;')
    st.html('<style>' + Path(__file__).with_name('styles.css').read_text(encoding='utf-8')
            + ':root {' + palette + '}</style>')


def badge(label, kind='unresolved'):
    # Both label and class are escaped/allowlisted; never execute customer HTML.
    kind = kind if kind in ('kb','resolved','unverified','unresolved','pending','high') else 'unresolved'
    st.markdown(f'<span class="badge badge-{kind}">{escape(str(label))}</span>', unsafe_allow_html=True)


def tier_badge(tier):
    badge(TIER_LABELS.get(tier, 'Unknown evidence tier'), tier)


def update_tags():
    previous = st.session_state.get('tag_lines', [])
    lines = [line for line in st.session_state.get('observations', '').splitlines() if line not in previous]
    current = [ACTION_TAGS[tag] for tag in st.session_state.get('tried_tags', [])]
    st.session_state.observations = '\n'.join(lines + current).strip()
    st.session_state.tag_lines = current


def move_source(key, direction):
    st.session_state[key] = st.session_state.get(key, 0) + direction


def select_saved_case(case_id):
    st.session_state.selected_saved_case = case_id
    st.session_state.case_picker = case_id
    st.session_state.case_details_open = True


def carousel(items, key, render, label='Source'):
    if not items:
        st.info('No evidence sources to display.')
        return
    fingerprint = repr([(item.get('id'), item.get('version')) for item in items])
    if st.session_state.get(key + '_items') != fingerprint:
        st.session_state[key] = 0
        st.session_state[key + '_items'] = fingerprint
    index = min(st.session_state.get(key, 0), len(items) - 1)
    previous, count, following = st.columns([1, 2, 1])
    previous.button('← Previous', key=key+'_previous', disabled=index == 0, use_container_width=True,
                    on_click=move_source, args=(key, -1))
    following.button('Next →', key=key+'_next', disabled=index == len(items)-1, use_container_width=True,
                     on_click=move_source, args=(key, 1))
    st.session_state[key] = index
    count.caption(f'{label}: {index + 1} of {len(items)}')
    with st.container(border=True, key=key + '_card_' + str(index)):
        render(items[index])


WAITING = '<div class="waiting" role="status" aria-live="polite"><b>Preparing your response…</b><div class="skeleton"></div></div>'


def classification_view(classification):
    st.table([{'Detail': key.capitalize(), 'Suggested value': str(classification.get(key, 'unknown')).replace('_', ' ')}
              for key in ('product', 'category', 'severity', 'sentiment')])
    if classification.get('symptoms'):
        st.caption('Reported symptoms')
        for symptom in classification['symptoms']: text(symptom)
    for action in classification.get('attempted_actions', []):
        text(str(action.get('action_id', '')).replace('_', ' ') + ' — ' + action.get('outcome', 'unknown'))
        text(action.get('evidence', ''))
    if classification.get('churn_risk'):
        st.warning('Cancellation risk reported')
        text(classification.get('churn_evidence', ''))


def text(value):
    # Render untrusted customer/evidence text without interpreting Markdown or HTML.
    st.text(str(value))


def search_hit_view(hit, mode):
    """Show existing retrieval scores without implying answer correctness."""
    source_card(hit['record'])
    score = hit.get('score')
    if score is not None:
        labels = {'keyword':'Keyword match (BM25)', 'semantic':'Meaning similarity (cosine)',
                  'hybrid':'Combined ranking (RRF)'}
        with st.expander('Match details'):
            st.caption(f"{labels[mode]}: {score:.4f}")
            if mode == 'hybrid':
                for name, component in hit.get('components', {}).items():
                    label = 'Keyword match (BM25)' if name == 'keyword' else 'Meaning similarity (cosine)'
                    st.caption(f"{label}: {component['score']:.4f} · rank {component['rank']}")
                st.caption('Combines keyword and meaning-based ranks. Small values are normal; this is not a percentage.')
            elif mode == 'semantic':
                st.caption('Higher values mean closer meaning. This is not a probability or a percentage of correctness.')
            else:
                st.caption('Higher values mean stronger word matches. BM25 has no fixed maximum.')
            st.caption('Compare scores within the same search and mode. Relevance does not prove a fix will work.')


def source_card(record):
    text(record.get('title', record['id']))
    tier_badge(record.get('evidence_tier', 'unknown'))
    st.caption(f"{record['id']} · version {record.get('version', 'unknown')}")
    with st.expander('Read source'):
        source_view(record)


def source_view(record):
    st.caption(f"{record['id']} · version {record.get('version', 'unknown')}")
    text(record.get('title', record['id']))
    tier = record.get('evidence_tier', 'unknown')
    tier_badge(tier)
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
