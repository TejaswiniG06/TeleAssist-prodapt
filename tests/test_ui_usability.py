"""UI regression checks for clarification, device context, card navigation and evidence forms."""
from copy import deepcopy
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest
from frontend.client import DashboardClient, DashboardError
from teleassist.common.access import AccessPolicy
from teleassist.services.combined import create_app


class NoProvider:
    configured = False


class Encoder:
    def encode(self, texts): return [[1, 0] for _ in texts]


class UsabilityTests(unittest.TestCase):
    def test_state_question_has_neutral_message_and_no_answer_can_end_clarification(self):
        calls = []
        question = 'Is the SIM currently inserted in the phone?'
        def send(client, path, payload=None, **kwargs):
            calls.append(deepcopy(payload))
            pending = len(calls) == 1
            return {'status':'clarification' if pending else 'escalation',
                    'answer':question if pending else 'The current state is confirmed. Refer to authorized support.',
                    'questions':[question] if pending else [], 'classification':{},
                    'masked_complaint':payload['complaint'], 'citations':[], 'mask_counts':{},
                    'steps':[], 'query_mode':payload['query_mode'], 'generation':'fallback',
                    'reason':'state_confirmation_required' if pending else 'no_applicable_evidence'}
        with patch.object(DashboardClient, 'request', send):
            app = AppTest.from_string('from frontend.views.agent import assistant\nfrom frontend.client import DashboardClient\nassistant(DashboardClient())').run()
            app.text_area(key='complaint').set_value('My mobile cannot call. I removed the SIM.')
            next(b for b in app.button if b.label == 'Prepare troubleshooting draft').click().run()
            self.assertFalse(app.warning)
            self.assertTrue(any('Confirm the current' in item.value for item in app.info))
            next(item for item in app.text_area if item.label == question).set_value('no')
            next(b for b in app.button if b.label == 'Continue').click().run()
            self.assertFalse(app.exception)
            self.assertIn(question + '\nAnswer: no', calls[-1]['observations'])
            self.assertFalse(any(item.label == question for item in app.text_area))
            self.assertTrue(any(item.value == 'A support specialist should review this' for item in app.subheader))

    def test_device_clarification_continues_original_case_and_new_case_clears_answers(self):
        calls = []
        def send(client, path, payload=None, **kwargs):
            calls.append(deepcopy(payload))
            return {'status':'clarification', 'answer':'Which lights are on?', 'questions':['Which lights are on?'],
                    'classification':{'product':'broadband','category':'unknown'}, 'masked_complaint':payload['complaint'],
                    'citations':[], 'mask_counts':{}, 'query_mode':payload['query_mode']}
        with patch.object(DashboardClient, 'request', send):
            app = AppTest.from_string('from frontend.views.agent import assistant\nfrom frontend.client import DashboardClient\nassistant(DashboardClient())').run()
            app.text_area(key='complaint').set_value('My home internet keeps dropping.')
            app.text_area(key='observations').set_value('Restarting did not help.')
            app.selectbox(key='device').select('Other').run()
            app.text_input(key='other_device').set_value('Mesh satellite')
            next(b for b in app.button if b.label == 'Prepare troubleshooting draft').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(calls[0]['observations'], 'Restarting did not help.\nDevice involved: Mesh satellite')
            next(b for b in app.button if b.label == 'Continue').click().run()
            self.assertEqual(len(calls), 1)  # Empty answers never consume an API call.
            next(x for x in app.text_area if x.label == 'Which lights are on?').set_value('The LOS light is red.')
            next(b for b in app.button if b.label == 'Continue').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(calls[1]['complaint'], calls[0]['complaint'])
            self.assertEqual(calls[1]['observations'], calls[0]['observations'] + '\nWhich lights are on?\nAnswer: The LOS light is red.')
            self.assertEqual(next(x for x in app.text_area if x.label == 'Which lights are on?').value, '')
            next(b for b in app.button if b.label == 'Start another case').click().run()
            self.assertEqual(app.selectbox(key='device').value, 'Not sure')
            self.assertEqual(app.text_area(key='observations').value, '')
            self.assertNotIn('case_result', app.session_state)

    def test_question_fields_are_unique_and_answers_keep_their_context(self):
        calls = []
        questions = ['Does it affect all devices?', 'Is the LOS light on?']
        def send(client, path, payload=None, **kwargs):
            calls.append(deepcopy(payload))
            return {'status':'clarification', 'answer':' '.join(questions), 'questions':questions + [questions[0]],
                    'classification':{}, 'masked_complaint':payload['complaint'], 'citations':[],
                    'query_mode':payload['query_mode']}
        with patch.object(DashboardClient, 'request', send):
            app = AppTest.from_string('from frontend.views.agent import assistant\nfrom frontend.client import DashboardClient\nassistant(DashboardClient())').run()
            app.text_area(key='complaint').set_value('My fiber disconnects every night.')
            next(b for b in app.button if b.label == 'Prepare troubleshooting draft').click().run()
            self.assertEqual([x.label for x in app.text_area if x.label in questions], questions)
            self.assertFalse(any(x.value == ' '.join(questions) for x in app.text))
            next(x for x in app.text_area if x.label == questions[0]).set_value('Yes, all devices.')
            next(x for x in app.text_area if x.label == questions[1]).set_value('No, it is off.')
            next(b for b in app.button if b.label == 'Continue').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(calls[-1]['observations'], 'Does it affect all devices?\nAnswer: Yes, all devices.\nIs the LOS light on?\nAnswer: No, it is off.')
            self.assertEqual(calls[-1]['complaint'], calls[0]['complaint'])

    def test_open_card_survives_existing_picker_value(self):
        def send(client, path, payload=None, **kwargs):
            if path.startswith('/cases?'):
                return {'cases':[{'id':'case-one','complaint':'First complaint','status':'pending'},
                                 {'id':'case-two','complaint':'Second complaint','status':'pending'}], 'notice':''}
            case_id = path.split('/')[-1]
            return {'id':case_id,'revision':1,'status':'pending','complaint':case_id + ' details',
                    'observations':'','draft':{'answer':'Need more details','classification':{}}, 'events':[]}
        with patch.object(DashboardClient, 'request', send):
            app = AppTest.from_string('from frontend.views.cases import saved_cases\nfrom frontend.client import DashboardClient\nsaved_cases(DashboardClient())').run()
            self.assertEqual(app.selectbox(key='case_picker').value, 'case-one')
            app.button(key='open_case-two').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.selectbox(key='case_picker').value, 'case-two')
            self.assertTrue(any(x.value == 'case-two details' for x in app.text))
            self.assertFalse(any(b.label == 'Open case' for b in app.button))
            next(b for b in app.button if b.label == '← Back to recent cases').click().run()
            self.assertTrue(any(b.label == 'Open case' for b in app.button))

    def test_theme_change_preserves_complaint_and_makes_no_requests(self):
        with patch.object(DashboardClient, 'request', side_effect=AssertionError('Unexpected API call')):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1]/'dashboard.py')).run()
            next(b for b in app.button if b.label == 'Open Support Agent workspace').click().run()
            app.text_area(key='complaint').set_value('My mobile data will not load.')
            app.radio(key='appearance').set_value('Dark').run()
            self.assertFalse(app.exception)
            self.assertEqual(app.text_area(key='complaint').value, 'My mobile data will not load.')
            self.assertEqual(app.session_state['appearance'], 'Dark')
            self.assertTrue(any(x.label == 'Load an example — optional' and not x.proto.expanded for x in app.expander))

    def test_evidence_forms_add_update_retire_and_reject_stale_version(self):
        with tempfile.TemporaryDirectory() as folder:
            app_api = create_app(encoder=Encoder(), provider=NoProvider(), include_public=False,
                access=AccessPolicy('required','agent','editor'), state_path=Path(folder)/'evidence.json',
                case_path=Path(folder)/'cases.sqlite3')
            with TestClient(app_api) as backend:
                def send(client,path,payload=None,**kwargs):
                    response=backend.request('POST' if payload is not None else 'GET',path,
                        json=payload,headers={'X-API-Key':'editor'})
                    if response.status_code>=400: raise DashboardError(str(response.json()['detail']),response.status_code)
                    return response.json()
                def wait_job(app):
                    job_id=app.session_state['last_job']
                    for _ in range(250):
                        job=backend.get('/admin/jobs/'+job_id,headers={'X-API-Key':'editor'}).json()
                        if job['status'] in ('published','failed'): break
                        time.sleep(.02)
                    self.assertEqual(job['status'],'published')
                with patch.object(DashboardClient,'request',send):
                    app=AppTest.from_string('from frontend.views.evidence import editor_evidence\nfrom frontend.client import DashboardClient, DashboardError\nimport streamlit as st\ntry: editor_evidence(DashboardClient())\nexcept DashboardError as error: st.error(str(error))').run()
                    next(b for b in app.button if b.label=='Start new evidence record').click().run()
                    source_id=app.session_state['editing_source']['record']['id']
                    next(x for x in app.text_input if x.label=='Title').set_value('Fictional FORM901 power check')
                    next(x for x in app.text_input if x.label=='Issue category').set_value('no connection')
                    next(x for x in app.text_area if x.label=='When does this guidance apply?').set_value('Router is offline and its power light is off.')
                    next(x for x in app.text_area if x.label=='Steps — one per line').set_value('Check whether the router power cable is connected.')
                    next(x for x in app.text_area if x.label=='Action names — one per line').set_value('check_power')
                    next(x for x in app.text_area if x.label=='When to use each step — one per line').set_value('Power light is off.')
                    next(x for x in app.checkbox if x.label=='I checked this content, its origin and any reported outcome').check()
                    next(b for b in app.button if b.label=='Publish evidence update').click().run()
                    self.assertFalse(app.exception)
                    wait_job(app)
                    # The open form retains its reviewed versions; it cannot overwrite newer evidence.
                    next(b for b in app.button if b.label=='Publish evidence update').click().run()
                    self.assertFalse(app.exception)
                    self.assertTrue(any('Index version changed' in error.value for error in app.error))
                    app=AppTest.from_string('from frontend.views.evidence import editor_evidence\nfrom frontend.client import DashboardClient, DashboardError\nimport streamlit as st\ntry: editor_evidence(DashboardClient())\nexcept DashboardError as error: st.error(str(error))').run()
                    app.radio(key='evidence_operation').set_value('Update').run()
                    next(x for x in app.text_input if x.label=='Source reference to update').set_value(source_id)
                    next(b for b in app.button if b.label=='Load source').click().run()
                    next(x for x in app.text_input if x.label=='Title').set_value('Fictional FORM901 updated power check')
                    next(x for x in app.checkbox if x.label=='I checked this content, its origin and any reported outcome').check()
                    next(b for b in app.button if b.label=='Publish evidence update').click().run()
                    self.assertFalse(app.exception)
                    wait_job(app)
                    app.radio(key='evidence_operation').set_value('Retire').run()
                    next(x for x in app.text_input if x.label=='Source reference to retire').set_value(source_id)
                    next(b for b in app.button if b.label=='Load source').click().run()
                    next(x for x in app.checkbox if x.label.startswith('Remove this source')).check()
                    next(b for b in app.button if b.label=='Retire source').click().run()
                    self.assertFalse(app.exception)
                    wait_job(app)
                    self.assertEqual(backend.get('/sources/'+source_id,headers={'X-API-Key':'agent'}).status_code,404)
                    self.assertEqual(backend.get('/sources/'+source_id+'?version=1',headers={'X-API-Key':'agent'}).status_code,200)

    def test_health_displays_surviving_service_when_other_is_down(self):
        def send(client,path,payload=None,editor=False):
            if not editor: raise DashboardError('Cannot reach API',503)
            if path=='/health': return {'active_sources':230,'semantic_state':'ready','generation_configured':False}
            if path=='/ready': return {'status':'ready'}
            return {'latency_ms':{},'http_errors':{},'inflight':1}
        with patch.object(DashboardClient,'request',send), patch.dict('os.environ',{'TELEASSIST_API_URL':'http://resolution:8002','TELEASSIST_EDITOR_URL':'http://retrieval:8001'}):
            app=AppTest.from_string('from frontend.views.health import health\nfrom frontend.client import DashboardClient\nhealth(DashboardClient())').run()
            self.assertFalse(app.exception)
            self.assertTrue(any('Resolution is unavailable' in error.value for error in app.error))
            self.assertEqual(app.metric[0].value,'230')


if __name__=='__main__': unittest.main()
