import json
from pathlib import Path
import tempfile
import unittest
from fastapi.testclient import TestClient
from fastapi import HTTPException
from access import AccessPolicy
from api import create_app


class NoProvider:
    configured = False


class AccessTests(unittest.TestCase):
    def test_required_mode_fails_closed(self):
        for kwargs in ({'mode':'required'}, {'mode':'required','agent_key':'a'},
                       {'agent_key':'same','editor_key':'same'}, {'mode':'typo'}):
            with self.assertRaises(ValueError):
                AccessPolicy(**kwargs)

    def test_roles_protect_services_and_editor_access(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'data.json'
            path.write_text(json.dumps([{'id':'a','version':1,'status':'active','title':'router',
                                         'product':'broadband','record_type':'article'}]))
            policy = AccessPolicy('required', 'agent-test', 'editor-test')
            with TestClient(create_app(path, provider=NoProvider(), access=policy)) as client:
                self.assertEqual(client.get('/health').status_code, 200)
                for key in (None, 'wrong'):
                    headers = {'X-API-Key':key} if key else {}
                    self.assertEqual(client.post('/search', json={'query':'router','mode':'keyword'},headers=headers).status_code,401)
                    self.assertEqual(client.get('/sources/a',headers=headers).status_code,401)
                    self.assertEqual(client.post('/resolve',json={'complaint':'router offline'},headers=headers).status_code,401)
                agent = {'X-API-Key':'agent-test'}
                self.assertEqual(client.get('/sources/a',headers=agent).status_code,200)
                self.assertEqual(client.get('/admin/access',headers=agent).status_code,403)
                self.assertEqual(client.get('/admin/access',headers={'X-API-Key':'editor-test'}).status_code,200)
                self.assertNotIn('editor-test',client.get('/health').text)

    def test_local_demo_cannot_edit(self):
        policy = AccessPolicy()
        self.assertEqual(policy.agent(None),'local_agent')
        with self.assertRaises(HTTPException) as caught:
            policy.editor(None)
        self.assertEqual(caught.exception.status_code,503)

    def test_non_ascii_wrong_key_is_unauthorized(self):
        policy=AccessPolicy('required','agent','editor')
        with self.assertRaises(HTTPException) as caught:
            policy.agent('你好')
        self.assertEqual(caught.exception.status_code,401)
