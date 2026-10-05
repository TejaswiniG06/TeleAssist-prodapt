import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import httpx
from fastapi.testclient import TestClient
from teleassist.common.access import AccessPolicy
from teleassist.services.retrieval import create_retrieval_app
from teleassist.services.resolution import create_resolution_app, RemoteEvidence


class NoProvider:
    configured=False


class SplitTests(unittest.TestCase):
    def test_no_applicable_evidence_reaches_shared_topics_but_monitor_outage_is_safe(self):
        observed = []
        def forward(request):
            observed.append(request)
            return httpx.Response(200, json={'recorded':True})
        result = {'status':'clarification', 'generation':'fallback', 'reason':'no_applicable_evidence',
                  'masked_complaint':'Satellite dish loses signal in rain. Contact [EMAIL].'}
        app = create_resolution_app(provider=NoProvider(), access=AccessPolicy(),
                                    transport=httpx.MockTransport(forward))
        with patch('teleassist.services.resolution.Resolver.resolve', return_value=result), TestClient(app) as client:
            self.assertEqual(client.post('/resolve', json={'complaint':'Satellite dish loses signal.'}).json(),
                             {**result, 'query_mode':'enriched'})
            self.assertEqual(observed[0].url.path, '/topics/observations')
            self.assertEqual(json.loads(observed[0].content)['complaint'], result['masked_complaint'])
            client.post('/resolve', json={'complaint':'Satellite dish loses signal.', 'exclude_source_ids':['a']})
            self.assertEqual(len(observed), 1)
        def fail(request):
            raise httpx.ConnectError('private diagnostics')
        app = create_resolution_app(provider=NoProvider(), access=AccessPolicy(),transport=httpx.MockTransport(fail))
        with patch('teleassist.services.resolution.Resolver.resolve', return_value=result), TestClient(app) as client:
            response = client.post('/resolve', json={'complaint':'Satellite dish loses signal.'})
            self.assertEqual(response.status_code, 200)
            self.assertNotIn('private diagnostics', response.text)

    def test_http_contract_and_roles(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'data.json'
            path.write_text(json.dumps([dict(id='a',version=1,status='active',title='router',category='no_connection',record_type='article',product='broadband')]))
            retrieval=create_retrieval_app(data_path=path,access=AccessPolicy('required','service-agent','editor'))
            with TestClient(retrieval) as upstream:
                def forward(request):
                    response=upstream.request(request.method,request.url.raw_path.decode(),content=request.content,headers=dict(request.headers))
                    return httpx.Response(response.status_code,content=response.content)
                resolution=create_resolution_app('http://retrieval.test',retrieval_key='service-agent',provider=NoProvider(),
                                                   access=AccessPolicy('required','user-agent','user-editor'),transport=httpx.MockTransport(forward))
                with TestClient(resolution) as client:
                    headers={'X-API-Key':'user-agent'}
                    self.assertEqual(client.post('/search',json={'query':'router','mode':'keyword'}).status_code,401)
                    result=client.post('/search',json={'query':'router','mode':'keyword'},headers=headers)
                    self.assertEqual(result.json()['results'][0]['id'],'a')
                    self.assertEqual(client.get('/sources/a?version=1',headers=headers).status_code,200)
                    self.assertEqual(client.post('/resolve',json={'complaint':'router offline'},headers=headers).json()['reason'],'generation_not_configured')
                    self.assertEqual(client.post('/admin/ingest',json={},headers=headers).status_code,404)
                    self.assertFalse(client.get('/health').json()['generation_configured'])
                self.assertEqual(upstream.post('/resolve',json={'complaint':'router'}).status_code,404)
                self.assertEqual(upstream.post('/search',json={'query':'router','mode':'keyword','expected_index_version':99},headers={'X-API-Key':'service-agent'}).status_code,409)

    def test_retrieval_outage_clarifies_without_private_diagnostics(self):
        def fail(request):
            raise httpx.ConnectError('private server details')
        app=create_resolution_app(provider=NoProvider(),access=AccessPolicy(),transport=httpx.MockTransport(fail))
        with TestClient(app) as client:
            self.assertEqual(client.get('/live').status_code,200)
            self.assertEqual(client.get('/ready').status_code,503)
            response=client.post('/resolve',json={'complaint':'router offline for example@example.com',
                                                'observations':'Router reboot failed. Contact other@example.com.'})
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['reason'],'retrieval_unavailable')
            self.assertNotIn('private server details',response.text)
            self.assertNotIn('example@example.com',response.text)
            self.assertEqual(response.json()['mask_counts']['EMAIL'],2)
            self.assertEqual(response.json()['classification']['attempted_actions'][0]['action_id'],'restart_router')
