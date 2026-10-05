"""Role choice and navigation; screen implementations live in frontend.views."""
import streamlit as st
from frontend.client import DashboardClient, DashboardError
from frontend.components import apply_style
from frontend.views.agent import assistant, reset_case
from frontend.views.cases import saved_cases
from frontend.views.evidence import evidence, editor_evidence
from frontend.views.topics import topics_view
from frontend.views.health import health


def switch_role():
    reset_case()
    for name in ('application_key', 'identity', 'search_result', 'last_job', 'selected_saved_case', 'case_picker', 'case_details_open', 'editing_source'):
        st.session_state.pop(name, None)
    st.session_state.view_role = 'landing'


def landing():
    st.markdown('<div class="eyebrow">Evidence-backed telecom support</div>', unsafe_allow_html=True)
    st.title('A clearer path from complaint to resolution')
    st.markdown('<p class="intro">Prepare useful responses, understand what has already been tried, and keep your support knowledge growing. Choose your workspace to begin.</p>', unsafe_allow_html=True)
    left, right = st.columns(2, gap='large')
    with left, st.container(border=True, key='role_agent'):
        st.markdown('### 🎧 Support Agent')
        st.write('Handle a complaint, inspect evidence and follow up on saved cases.')
        st.caption('Local demo access is available without a key. Authenticated deployments require an application key.')
        if st.button('Open Support Agent workspace', type='primary', use_container_width=True):
            st.session_state.view_role = 'agent'; st.rerun()
    with right, st.container(border=True, key='role_editor'):
        st.markdown('### 📚 Knowledge Editor')
        st.write('Manage evidence, review case outcomes, assess topics and inspect service health.')
        st.caption('An editor application key is required. This choice does not grant permissions.')
        if st.button('Open Knowledge Editor workspace', use_container_width=True):
            st.session_state.view_role = 'editor_login'; st.rerun()


def main():
    st.set_page_config(page_title='TeleAssist · Support workspace', page_icon='📡', layout='wide')
    brand, theme, control = st.columns([4, 2, 1])
    brand.markdown('### 📡 TeleAssist')
    theme.radio('Appearance', ['Light', 'Dark'], key='appearance', horizontal=True)
    apply_style()
    role = st.session_state.get('view_role', 'landing')
    if role != 'landing':
        control.button('Switch role', on_click=switch_role, use_container_width=True)
    if role == 'landing':
        landing(); return
    if role == 'editor_login':
        st.title('Open your editor workspace')
        st.caption('Use the application editor key configured on your backend. Never enter the Gemini provider key here.')
        with st.form('editor_login'):
            st.text_input('Editor application key', type='password', key='application_key')
            login = st.form_submit_button('Verify editor access', type='primary')
        if login:
            try:
                verified = DashboardClient(st.session_state.get('application_key', '')).request('/admin/access', editor=True)
                if verified.get('role') != 'editor': raise DashboardError('Editor access was not granted.')
                st.session_state.view_role = 'editor'; st.rerun()
            except DashboardError as error:
                st.error(str(error))
        return
    with st.expander('Advanced · access permissions'):
        with st.form('access_settings'):
            st.text_input('Access key — only if required', type='password', key='application_key',
                          help='TeleAssist agent/editor key, not the Gemini key. Leave blank for the local agent demo.')
            st.form_submit_button('Apply access key')
        st.caption('Agents can leave this blank in the local demo. An editor key permits shared knowledge changes. This is not your Gemini key.')
    key = st.session_state.get('application_key', '')
    if st.session_state.get('identity', '') != key:
        reset_case()
        for name in ('search_result','last_job','selected_saved_case','case_picker','case_details_open','editing_source'):
            st.session_state.pop(name, None)
        st.session_state.identity = key
    client = DashboardClient(key)
    try:
        editor = False
        if role == 'editor':
            editor = client.request('/admin/access', editor=True).get('role') == 'editor'
            if not editor: raise DashboardError('Editor access is required. Switch role to sign in again.')
        if editor:
            pages = [st.Page(lambda: editor_evidence(client), title='Evidence', url_path='evidence', default=True),
                     st.Page(lambda: saved_cases(client, True), title='Saved Cases', url_path='cases'),
                     st.Page(lambda: topics_view(client), title='Topics', url_path='topics'),
                     st.Page(lambda: health(client), title='Health', url_path='health')]
        else:
            pages = [st.Page(lambda: assistant(client), title='Support Assistant', url_path='assistant', default=True),
                     st.Page(lambda: saved_cases(client), title='Saved Cases', url_path='cases'),
                     st.Page(lambda: evidence(client), title='Evidence Explorer', url_path='evidence')]
        st.navigation(pages, position='top').run()
    except DashboardError as error:
        st.error(str(error))
