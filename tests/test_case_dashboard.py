"""Dashboard case capture, actual outcomes and reviewed publication use the real API."""
from contextlib import ExitStack
import httpx
import re
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest
from teleassist.common.access import AccessPolicy
from teleassist.services.combined import create_app
from teleassist.services.retrieval import create_retrieval_app
from teleassist.services.resolution import create_resolution_app
from frontend.client import DashboardClient, DashboardError


class Encoder:
    def encode(self, texts):
        return [[1, 0] for _ in texts]


class NoProvider:
    configured = False


class CaseDashboardTests(unittest.TestCase):
    def test_save_outcome_review_and_future_search_via_real_api(self):
        self.case_workflow(split=False)

    def test_same_dashboard_workflow_with_separate_services(self):
        self.case_workflow(split=True)

    def case_workflow(self, split):
        with tempfile.TemporaryDirectory() as folder:
            factory = create_retrieval_app if split else create_app
            api = factory(encoder=Encoder(), provider=NoProvider(), include_public=False,
                access=AccessPolicy('required', 'agent', 'editor'),
                case_path=Path(folder)/'cases.sqlite3', state_path=Path(folder)/'evidence.json')
            with ExitStack() as stack:
                backend = stack.enter_context(TestClient(api))
                resolution = backend
                if split:
                    def forward(request):
                        response = backend.request(request.method, request.url.raw_path.decode(),
                            content=request.content, headers=dict(request.headers))
                        return httpx.Response(response.status_code, content=response.content)
                    resolution = stack.enter_context(TestClient(create_resolution_app(
                        'http://retrieval.test', retrieval_key='agent', provider=NoProvider(),
                        access=AccessPolicy('required', 'agent', 'editor'), transport=httpx.MockTransport(forward))))
                    self.assertEqual(backend.post('/resolve', json={'complaint':'test'}).status_code, 404)
                role = ['agent']
                calls = []
                def send(client, path, payload=None, **kwargs):
                    calls.append((path, payload, kwargs))
                    if '/cases' in path:
                        self.assertTrue(kwargs.get('editor'))  # Correct evidence-service address in split mode.
                    target = backend if kwargs.get('editor') else resolution
                    response = target.request('POST' if payload is not None else 'GET', path,
                        json=payload, headers={'X-API-Key':role[0]})
                    if response.status_code >= 400:
                        raise DashboardError(str(response.json()['detail']), response.status_code)
                    return response.json()
                with patch.object(DashboardClient, 'request', send):
                    assistant = AppTest.from_string('from frontend.views.agent import assistant\nfrom frontend.client import DashboardClient\nassistant(DashboardClient())').run()
                    assistant.text_area(key='complaint').set_value('Fiber CASEABC901 disconnected. Email demo@example.com.')
                    assistant.text_area(key='observations').set_value('ONT alarm illuminated.')
                    next(b for b in assistant.button if b.label == 'Prepare troubleshooting draft').click().run()
                    self.assertFalse(assistant.exception)
                    next(b for b in assistant.button if b.label == 'Save case for follow-up').click().run()
                    self.assertFalse(assistant.exception)
                    case_id = assistant.session_state['saved_case_id']
                    saved = backend.get('/cases/' + case_id, headers={'X-API-Key':'agent'}).json()
                    self.assertEqual(saved['status'], 'pending')
                    self.assertNotIn('demo@example.com', saved['complaint'])
                    next(b for b in assistant.button if b.label == 'Start another case').click().run()
                    self.assertNotIn('case_result', assistant.session_state)
                    self.assertEqual(backend.get('/cases/' + case_id, headers={'X-API-Key':'agent'}).status_code, 200)
                    cases = AppTest.from_string('from frontend.views.cases import saved_cases\nfrom frontend.client import DashboardClient\nsaved_cases(DashboardClient())', default_timeout=10).run()
                    self.assertFalse(cases.exception)
                    self.assertFalse(any(b.label == 'Approve and publish' for b in cases.button))
                    next(x for x in cases.text_area if x.label.startswith('Actions actually')).set_value('Technician replaced the damaged optical connector.')
                    next(x for x in cases.text_area if x.label == 'What confirms whether the issue was fixed?').set_value('Customer confirmed stable connection for two days.')
                    cases.checkbox[0].check()
                    next(b for b in cases.button if b.label == 'Record actual outcome').click().run()
                    self.assertFalse(cases.exception)
                    self.assertTrue(any('An editor must review' in x.value for x in cases.info))
                    role[0] = 'editor'
                    editor = AppTest.from_string('from frontend.views.cases import saved_cases\nfrom frontend.client import DashboardClient\nsaved_cases(DashboardClient(), editor=True)').run()
                    self.assertFalse(editor.exception)
                    category_box = next(x for x in editor.selectbox if x.label == 'Reviewed category')
                    self.assertTrue(all(re.fullmatch(r'[a-z][a-z0-9_]{0,79}', option) for option in category_box.options))
                    next(x for x in editor.text_input if x.label == 'Historical ticket title').set_value('Reviewed CASEABC901 optical connector case')
                    next(x for x in editor.selectbox if x.label == 'Reviewed category').select('no_connection')
                    next(x for x in editor.text_area if x.label.startswith('When do')).set_value('ONT alarm illuminated with technician-confirmed connector damage.')
                    next(x for x in editor.text_area if x.label == 'Review rationale').set_value('Checked actions and customer confirmation against the reported outcome.')
                    next(x for x in editor.checkbox if x.label.startswith('I reviewed')).check()
                    next(b for b in editor.button if b.label == 'Approve and publish').click().run()
                    self.assertFalse(editor.exception)
                    deadline = time.monotonic() + 5
                    while time.monotonic() < deadline:
                        saved = backend.get('/cases/' + case_id, headers={'X-API-Key':'editor'}).json()
                        if saved['status'] == 'published':
                            break
                        time.sleep(.01)
                    editor.run()
                    self.assertFalse(editor.exception)
                    self.assertTrue(any('Published as historical evidence' in x.value for x in editor.success))
                    hits = backend.post('/search', json={'query':'CASEABC901', 'mode':'keyword'}, headers={'X-API-Key':'agent'}).json()
                    self.assertEqual(hits['results'][0]['id'], saved['publication']['source_id'])
                    self.assertEqual(sum(path == '/resolve' for path, _, _ in calls), 1)

    def test_empty_case_workspace_is_honest(self):
        with patch.object(DashboardClient, 'request', return_value={'cases':[], 'notice':'Pending cases are not evidence.'}):
            cases = AppTest.from_string('from frontend.views.cases import saved_cases\nfrom frontend.client import DashboardClient\nsaved_cases(DashboardClient())', default_timeout=10).run()
            self.assertFalse(cases.exception)
            self.assertTrue(any('No cases saved yet' in x.value for x in cases.info))


if __name__ == '__main__':
    unittest.main()
