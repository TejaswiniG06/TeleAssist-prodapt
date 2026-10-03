import json
from pathlib import Path
import tempfile
import unittest
import httpx
from fastapi.testclient import TestClient
from access import AccessPolicy
from retrieval_api import create_retrieval_app
from resolution_api import create_resolution_app, RemoteEvidence


class NoProvider:
    configured=False


class SplitTests(unittest.TestCase):
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
