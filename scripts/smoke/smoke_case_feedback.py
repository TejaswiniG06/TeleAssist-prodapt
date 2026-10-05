"""Fictional case -> reported outcome -> reviewed history, with real local embeddings.

Uses isolated SQLite/catalog files, no LLM calls, and does not change live evidence.
"""
import json
from pathlib import Path
import tempfile
import time
from uuid import uuid4
from fastapi.testclient import TestClient
from teleassist.common.access import AccessPolicy
from teleassist.services.combined import create_app


class NoProvider:
    configured = False
    def generate(self, *args, **kwargs):
        raise AssertionError('This smoke check must not call an LLM.')


def run():
    agent, editor = {'X-API-Key':'smoke-agent'}, {'X-API-Key':'smoke-editor'}
    complaint = 'CASEFB901 fiber connection disconnects. The ONT optical LOS alarm blinks and all wired and Wi-Fi devices lose connectivity.'
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        def app():
            return create_app(provider=NoProvider(), access=AccessPolicy('required', 'smoke-agent', 'smoke-editor'),
                case_path=root/'cases.sqlite3', state_path=root/'evidence.json', cache_path=root/'embeddings.json')
        with TestClient(app()) as client:
            initial = client.get('/health').json()
            response = client.post('/cases', headers=agent, json={'request_id':uuid4().hex,
                'complaint':complaint, 'observations':'A technician identified physical optical connector damage.',
                'draft':{'status':'clarification', 'answer':'Pending fictional technician confirmation.',
                         'classification':{'product':'broadband', 'category':'no_connection'}}})
            response.raise_for_status(); case = response.json()
            pending = client.post('/search', headers=agent, json={'query':'CASEFB901', 'mode':'keyword'}).json()
            assert pending['results'] == [], 'Pending cases must not be retrieval evidence.'
            response = client.post('/cases/' + case['id'] + '/outcome', headers=agent,
                json={'expected_revision':case['revision'], 'outcome':'resolved', 'confirmed':True,
                      'actual_actions':['Technician replaced the damaged optical connector at the fiber ONT.'],
                      'outcome_evidence':'Fictional smoke case: customer confirmed stable connectivity for two days.'})
            response.raise_for_status(); case = response.json()
            response = client.post('/admin/cases/' + case['id'] + '/review', headers=editor,
                json={'expected_revision':case['revision'], 'expected_index_version':initial['index_version'],
                      'decision':'approve', 'confirmed':True, 'title':'Fictional CASEFB901 fiber ONT connector history',
                      'product':'broadband', 'category':'no_connection',
                      'applicability':'Optical LOS alarm and technician-confirmed physical connector damage.',
                      'rationale':'Fictional isolated smoke check of reported actions and explicit outcome.'})
            response.raise_for_status()
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                case = client.get('/cases/' + case['id'], headers=agent).json()
                if case['status'] != 'publishing':
                    break
                time.sleep(.1)
            assert case['status'] == 'published', case
            source_id = case['publication']['source_id']
            modes = {}
            for mode in ('keyword', 'semantic', 'hybrid'):
                response = client.post('/search', headers=agent, json={'query':complaint, 'mode':mode,
                    'product':'broadband', 'record_type':'resolved_ticket', 'limit':20})
                response.raise_for_status()
                ids = [hit['id'] for hit in response.json()['results']]
                assert source_id in ids, (mode, ids)
                modes[mode] = {'found':True, 'rank':ids.index(source_id) + 1}
            assert client.get('/health').json()['index_version'] == initial['index_version'] + 1
        with TestClient(app()) as client:
            restored = client.get('/cases/' + case['id'], headers=agent).json()
            assert restored['status'] == 'published'
            assert client.get('/sources/' + source_id, headers=agent).json()['outcome'] == 'resolved'
        print(json.dumps({'fictional_isolated_case':True, 'initial_sources':initial['active_sources'],
            'pending_not_indexed':True, 'reviewed_history':modes, 'restart_restored':True, 'llm_calls':0}, indent=2))


if __name__ == '__main__':
    run()
