"""Confirmed case outcomes enter retrieval only through editor-reviewed publication."""
import json
from pathlib import Path
import tempfile
import time
import unittest
from fastapi.testclient import TestClient
from teleassist.common.access import AccessPolicy
from teleassist.services.combined import create_app
from teleassist.cases.store import CaseStore


class Encoder:
    broken = False
    def encode(self, texts):
        if self.broken:
            raise RuntimeError('Private indexing error')
        return [[1, 0] for _ in texts]


class NoProvider:
    configured = False
    def generate(self, *args, **kwargs):
        raise AssertionError('Case operations must not call an LLM.')


def saved_case():
    return {'request_id':'a' * 32, 'complaint':'Fiber E901XYZ disconnects. Contact demo@example.com or 9876543210.',
            'observations':'The ONT alarm is illuminated.',
            'draft':{'status':'resolution', 'answer':'Suggested action, not a confirmed success.',
                     'classification':{'product':'broadband', 'category':'no_connection'}}}


def outcome(revision, result='resolved'):
    return {'expected_revision':revision, 'outcome':result,
            'actual_actions':['A technician replaced the damaged ONT optical connector.'],
            'outcome_evidence':'Customer confirmed stable connectivity for two days.', 'confirmed':True}


def review(revision, index=1, decision='approve'):
    return {'expected_revision':revision, 'decision':decision, 'confirmed':True,
            'rationale':'Reviewed technician actions and customer confirmation.',
            'expected_index_version':index, 'title':'Reviewed fiber E901XYZ case',
            'product':'broadband', 'category':'no_connection',
            'applicability':'ONT alarm illuminated and connector damage confirmed by a technician.'}


class CaseTests(unittest.TestCase):
    agent = {'X-API-Key':'agent'}
    editor = {'X-API-Key':'editor'}

    def app(self, folder, encoder=None):
        return create_app(encoder=encoder or Encoder(), provider=NoProvider(), include_public=False,
                          access=AccessPolicy('required', 'agent', 'editor'),
                          state_path=Path(folder)/'evidence.json', case_path=Path(folder)/'cases.sqlite3')

    def record(self, client, result='resolved'):
        case = client.post('/cases', json=saved_case(), headers=self.agent).json()
        response = client.post('/cases/' + case['id'] + '/outcome',
                               json=outcome(case['revision'], result), headers=self.agent)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def wait(self, client, case_id):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            case = client.get('/cases/' + case_id, headers=self.agent).json()
            if case['status'] != 'publishing':
                return case
            time.sleep(.01)
        self.fail('Publication did not finish.')

    def test_save_is_masked_persistent_idempotent_and_not_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            with TestClient(self.app(folder)) as client:
                count = client.get('/health').json()['active_sources']
                self.assertEqual(client.post('/cases', json=saved_case()).status_code, 401)
                response = client.post('/cases', json=saved_case(), headers=self.agent)
                self.assertEqual(response.status_code, 201)
                case = response.json()
                self.assertEqual(case['status'], 'pending')
                self.assertNotIn('demo@example.com', json.dumps(case))
                self.assertNotIn('9876543210', json.dumps(case))
                repeated = client.post('/cases', json=saved_case(), headers=self.agent).json()
                self.assertEqual(repeated['id'], case['id'])
                changed = dict(saved_case(), complaint='A different complaint')
                self.assertEqual(client.post('/cases', json=changed, headers=self.agent).status_code, 409)
                hits = client.post('/search', json={'query':'E901XYZ', 'mode':'keyword'}, headers=self.agent).json()
                self.assertEqual(hits['results'], [])
                self.assertEqual(client.get('/health').json()['active_sources'], count)
            with TestClient(self.app(folder)) as client:
                self.assertEqual(client.get('/cases/' + case['id'], headers=self.agent).json()['status'], 'pending')
                self.assertEqual(len(client.get('/cases', headers=self.agent).json()['cases']), 1)

    def test_actual_outcome_and_review_are_required_and_agent_cannot_publish(self):
        with tempfile.TemporaryDirectory() as folder, TestClient(self.app(folder)) as client:
            case = client.post('/cases', json=saved_case(), headers=self.agent).json()
            url = '/admin/cases/' + case['id'] + '/review'
            self.assertEqual(client.post(url, json=review(1), headers=self.editor).status_code, 409)
            self.assertEqual(client.post(url, json=review(1), headers=self.agent).status_code, 403)
            invalid = outcome(1); invalid['actual_actions'] = []
            self.assertEqual(client.post('/cases/' + case['id'] + '/outcome', json=invalid, headers=self.agent).status_code, 422)
            invalid = outcome(1); invalid['confirmed'] = False
            self.assertEqual(client.post('/cases/' + case['id'] + '/outcome', json=invalid, headers=self.agent).status_code, 422)
            confirmed = client.post('/cases/' + case['id'] + '/outcome', json=outcome(1), headers=self.agent).json()
            self.assertEqual(client.post('/cases/' + case['id'] + '/outcome', json=outcome(1), headers=self.agent).status_code, 409)
            self.assertEqual(client.post(url, json=review(confirmed['revision'], index=99), headers=self.editor).status_code, 409)
            invalid_review = review(confirmed['revision']); invalid_review['category'] = 'unreviewed_new_category'
            self.assertEqual(client.post(url, json=invalid_review, headers=self.editor).status_code, 422)

    def test_reviewed_resolution_becomes_searchable_without_restart_and_survives_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            with TestClient(self.app(folder)) as client:
                case = self.record(client)
                response = client.post('/admin/cases/' + case['id'] + '/review',
                                       json=review(case['revision']), headers=self.editor)
                self.assertEqual(response.status_code, 202)
                case = self.wait(client, case['id'])
                self.assertEqual(case['status'], 'published')
                source_id = case['publication']['source_id']
                result = client.post('/search', json={'query':'E901XYZ', 'mode':'keyword'}, headers=self.agent).json()
                self.assertEqual(result['results'][0]['id'], source_id)
                source = result['results'][0]['record']
                self.assertEqual(source['evidence_tier'], 'resolved')
                self.assertEqual(source['provenance'], 'reviewed_internal')
                self.assertIn('technician replaced', source['resolution_steps'][0]['instruction'])
                self.assertNotIn('Suggested action', json.dumps(source))
                self.assertEqual(client.post('/cases/' + case['id'] + '/outcome', json=outcome(case['revision']), headers=self.agent).status_code, 409)
                self.assertEqual(client.post('/admin/cases/' + case['id'] + '/review', json=review(case['revision'], 2), headers=self.editor).status_code, 409)
            with TestClient(self.app(folder)) as client:
                self.assertEqual(client.get('/cases/' + case['id'], headers=self.agent).json()['status'], 'published')
                self.assertEqual(client.get('/sources/' + source_id, headers=self.agent).json()['outcome'], 'resolved')

    def test_unresolved_and_rejected_cases_never_become_successful_history(self):
        with tempfile.TemporaryDirectory() as folder, TestClient(self.app(folder)) as client:
            case = self.record(client, 'not_resolved')
            response = client.post('/admin/cases/' + case['id'] + '/review',
                                   json=review(case['revision']), headers=self.editor)
            self.assertEqual(response.status_code, 202)
            case = self.wait(client, case['id'])
            source = client.get('/sources/' + case['publication']['source_id'], headers=self.agent).json()
            self.assertEqual(source['evidence_tier'], 'unresolved')
            self.assertEqual(source['resolution_steps'], [])
            second = dict(saved_case(), request_id='b' * 32)
            second = client.post('/cases', json=second, headers=self.agent).json()
            second = client.post('/cases/' + second['id'] + '/outcome', json=outcome(1), headers=self.agent).json()
            rejected = client.post('/admin/cases/' + second['id'] + '/review',
                                   json=review(second['revision'], 2, 'reject'), headers=self.editor).json()
            self.assertEqual(rejected['status'], 'rejected')
            self.assertIsNone(rejected['publication'])

    def test_failed_build_keeps_case_retryable_and_old_index_active(self):
        with tempfile.TemporaryDirectory() as folder:
            encoder = Encoder(); encoder.broken = True
            with TestClient(self.app(folder, encoder)) as client:
                count = client.get('/health').json()['active_sources']
                case = self.record(client)
                client.post('/admin/cases/' + case['id'] + '/review', json=review(case['revision']), headers=self.editor)
                case = self.wait(client, case['id'])
                self.assertEqual(case['status'], 'outcome_recorded')
                self.assertIn('did not complete', case['publication']['error'])
                self.assertEqual(client.get('/health').json()['active_sources'], count)
                encoder.broken = False
                response = client.post('/admin/cases/' + case['id'] + '/review', json=review(case['revision']), headers=self.editor)
                self.assertEqual(response.status_code, 202)
                self.assertEqual(self.wait(client, case['id'])['status'], 'published')

    def test_durable_publication_reconciles_missing_job_after_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            app = self.app(folder)
            with TestClient(app) as client:
                case = self.record(client)
                response = client.post('/admin/cases/' + case['id'] + '/review', json=review(case['revision']), headers=self.editor)
                self.assertEqual(response.status_code, 202)
            # Simulate the evidence committing before the ledger acknowledged publication.
            store = CaseStore(Path(folder)/'cases.sqlite3')
            case = store.get(case['id']); case['status'] = 'publishing'; store._write(case); store.close()
            with TestClient(self.app(folder)) as client:
                self.assertEqual(client.get('/cases/' + case['id'], headers=self.agent).json()['status'], 'published')

    def test_missing_unpublished_job_after_restart_returns_to_review(self):
        with tempfile.TemporaryDirectory() as folder:
            with TestClient(self.app(folder)) as client:
                case = self.record(client)
            store = CaseStore(Path(folder)/'cases.sqlite3')
            from teleassist.cases.store import CaseReview
            store.review(case['id'], CaseReview(**review(case['revision'])), 'editor')
            store.attach_job(case['id'], 'job-that-never-completed'); store.close()
            with TestClient(self.app(folder)) as client:
                case = client.get('/cases/' + case['id'], headers=self.agent).json()
                self.assertEqual(case['status'], 'outcome_recorded')
                self.assertTrue(case['publication']['error'])

    def test_review_fields_are_masked_before_storage(self):
        with tempfile.TemporaryDirectory() as folder, TestClient(self.app(folder)) as client:
            case = self.record(client)
            payload = review(case['revision']); payload['title'] += ' demo@example.com'
            response = client.post('/admin/cases/' + case['id'] + '/review', json=payload, headers=self.editor)
            self.assertEqual(response.status_code, 202)
            case = self.wait(client, case['id'])
            self.assertNotIn('demo@example.com', json.dumps(case))


if __name__ == '__main__':
    unittest.main()
