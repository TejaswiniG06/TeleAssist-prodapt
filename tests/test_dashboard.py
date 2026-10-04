"""Dashboard behaviour: access, independent cases, version reads and failures."""
from pathlib import Path
import unittest
import json
import time
from unittest.mock import patch
import httpx
from streamlit.testing.v1 import AppTest
from dashboard_client import DashboardClient, DashboardError


ROOT = Path(__file__).resolve().parents[1]


class DashboardTests(unittest.TestCase):
    def test_editor_screens_and_ingestion_use_real_api_contract(self):
        from fastapi.testclient import TestClient
        from access import AccessPolicy
        from api import create_app
        class Encoder:
            def encode(self, texts): return [[1,0] for _ in texts]
        class NoProvider:
            configured = False
        api = create_app(encoder=Encoder(),provider=NoProvider(),include_public=False,
                         access=AccessPolicy('required','test-agent','test-editor'))
        with TestClient(api) as backend:
            initial_count = backend.get('/health').json()['active_sources']
            def send(client,path,payload=None,**kwargs):
                response=backend.request('POST' if payload is not None else 'GET',path,
                    json=payload,headers={'X-API-Key':'test-editor'})
                if response.status_code>=400:
                    raise DashboardError(str(response.json()['detail']),response.status_code)
                return response.json()
            with patch.object(DashboardClient,'request',send):
                health=AppTest.from_string('from dashboard import health\nfrom dashboard_client import DashboardClient\nhealth(DashboardClient())').run()
                self.assertFalse(health.exception)
                self.assertEqual(health.metric[0].value,str(initial_count))
                knowledge=AppTest.from_string('from dashboard import knowledge\nfrom dashboard_client import DashboardClient\nknowledge(DashboardClient())').run()
                self.assertFalse(knowledge.exception)
                self.assertTrue(any('No topic proposals' in x.value for x in knowledge.info))
                record={'id':'KB-UI-TEST','title':'UI submitted guidance','record_type':'article',
                    'product':'broadband','category':'no_connection','provenance':'synthetic_demo',
                    'applicability':'Router has no connection.',
                    'steps':[{'action_id':'check_power','instruction':'Check whether the router has power.',
                              'condition':'Power state unknown.'}]}
                knowledge.text_area[0].set_value(json.dumps({'expected_index_version':1,
                    'changes':[{'expected_version':0,'record':record}]}))
                knowledge.checkbox[0].check()
                next(b for b in knowledge.button if b.label=='Submit indexing job').click().run()
                self.assertFalse(knowledge.exception)
                self.assertTrue(knowledge.success)
                job_id=knowledge.session_state['last_job']
                deadline=time.monotonic()+5
                while time.monotonic()<deadline:
                    job=backend.get('/admin/jobs/'+job_id,headers={'X-API-Key':'test-editor'}).json()
                    if job['status'] in ('published','failed'): break
                    time.sleep(.02)
                self.assertEqual(job['status'],'published')
                health.run()
                self.assertEqual(health.metric[0].value,str(initial_count + 1))
                self.assertEqual(health.metric[1].value,'2')

    def test_http_auth_and_exact_version(self):
        seen = []
        def handler(request):
            seen.append(request)
            return httpx.Response(200, json={'id':'KB-001','version':2})
        client = DashboardClient('application-test-key', httpx.MockTransport(handler))
        self.assertEqual(client.source('KB-001', 2)['version'], 2)
        self.assertEqual(seen[0].url.path, '/sources/KB-001')
        self.assertEqual(seen[0].url.params['version'], '2')
        self.assertEqual(seen[0].headers['X-API-Key'], 'application-test-key')

    def test_failures_do_not_report_success_or_leak_keys(self):
        for status in (401,403,409,503):
            client = DashboardClient('secret-test-key', httpx.MockTransport(
                lambda request: httpx.Response(status, json={'detail':'Unavailable'})))
            with self.assertRaises(DashboardError) as error:
                client.request('/admin/metrics', editor=True)
            self.assertEqual(error.exception.status, status)
            self.assertNotIn('secret-test-key', str(error.exception))
        def timeout(request):
            raise httpx.ReadTimeout('secret-test-key', request=request)
        with self.assertRaisesRegex(DashboardError, 'timed out'):
            DashboardClient('secret-test-key',httpx.MockTransport(timeout)).request('/resolve',{})

    def test_editor_uses_separate_configured_service(self):
        seen=[]
        def handler(request):
            seen.append(str(request.url))
            return httpx.Response(200,json={})
        with patch.dict('os.environ',{'TELEASSIST_API_URL':'http://resolution:8002',
                                      'TELEASSIST_EDITOR_URL':'http://retrieval:8001'}):
            client=DashboardClient(transport=httpx.MockTransport(handler))
            client.request('/health')
            client.request('/admin/topics',editor=True)
        self.assertEqual(seen,['http://resolution:8002/health','http://retrieval:8001/admin/topics'])

    def test_independent_cases_clear_and_error_recovery(self):
        submitted=[]
        def backend(client,path,payload=None,**kwargs):
            if path=='/admin/access': raise DashboardError('Editor required',403)
            if path=='/resolve':
                submitted.append(payload)
                return {'status':'clarification','answer':'Which devices are affected?',
                        'classification':{'product':'broadband','category':'unknown',
                                          'severity':'unknown','sentiment':'unknown',
                                          'churn_risk':'cancelling' in payload['complaint'],
                                          'churn_evidence':payload['complaint'] if 'cancelling' in payload['complaint'] else ''},
                        'masked_complaint':payload['complaint'],'citations':[],
                        'questions':[],'mask_counts':{},'generation':'fallback',
                        'reason':'generation_not_configured','citation_check':'no_steps'}
            raise AssertionError(path)
        with patch.object(DashboardClient,'request',backend):
            app=AppTest.from_file(str(ROOT/'dashboard.py')).run()
            self.assertFalse(app.exception)
            app.text_area(key='complaint').set_value('Slow broadband')
            app.text_area(key='observations').set_value('Restart failed')
            next(b for b in app.button if b.label=='Prepare response').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(submitted,[{'complaint':'Slow broadband','observations':'Restart failed','query_mode':'enriched'}])
            next(b for b in app.button if b.label=='New complaint').click().run()
            self.assertEqual(app.text_area(key='complaint').value,'')
            self.assertNotIn('case_result',app.session_state)
            app.text_area(key='complaint').set_value('Mobile has no signal')
            next(b for b in app.button if b.label=='Prepare response').click().run()
            self.assertEqual(submitted[-1],{'complaint':'Mobile has no signal','observations':'','query_mode':'enriched'})
            app.text_area(key='complaint').set_value("I'm cancelling my contract.")
            next(b for b in app.button if b.label=='Prepare response').click().run()
            self.assertTrue(any('Explicit cancellation threat' in x.value for x in app.warning))
            app.text_input(key='application_key').set_value('another-agent').run()
            self.assertNotIn('case_result',app.session_state)
            self.assertEqual(app.text_area(key='complaint').value,'')
            with patch.object(DashboardClient,'request',side_effect=DashboardError('API unavailable')):
                app.text_area(key='complaint').set_value('Test outage')
                next(b for b in app.button if b.label=='Prepare response').click().run()
                self.assertFalse(app.exception)
                self.assertTrue(any('API unavailable' in e.value for e in app.error))
                self.assertNotIn('case_result',app.session_state)


if __name__=='__main__':
    unittest.main()
