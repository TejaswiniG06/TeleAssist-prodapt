import json
from pathlib import Path
import tempfile
import unittest
from fastapi.testclient import TestClient
from teleassist.common.access import AccessPolicy
from teleassist.services.combined import create_app
from teleassist.common.monitoring import Metrics


class NoProvider:
    configured = False


class MonitoringTests(unittest.TestCase):
    def test_latency_samples_bounded_and_counters_complete(self):
        metrics = Metrics()
        for _ in range(300):
            metrics.begin()
            metrics.finish('/search',200,.01)
        result = metrics.snapshot()
        self.assertEqual(result['requests']['/search'],300)
        self.assertEqual(result['latency_ms']['/search']['sample_count'],256)
        self.assertEqual(result['inflight'],0)
        self.assertGreater(result['process']['rss_bytes'],0)

    def test_api_readiness_errors_and_fallbacks_without_raw_text(self):
        class Encoder:
            def encode(self,texts):
                return [[1,0] for _ in texts]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'data.json'
            path.write_text(json.dumps([dict(id='a',version=1,status='active',title='router',record_type='article',product='broadband')]))
            with TestClient(create_app(path,Encoder(),provider=NoProvider(),access=AccessPolicy(editor_key='editor'))) as client:
                self.assertEqual(client.get('/live').status_code,200)
                self.assertEqual(client.get('/ready').status_code,200)
                self.assertEqual(client.get('/ready?require_semantic=true').status_code,503)
                self.assertEqual(client.get('/admin/metrics').status_code,403)
                client.post('/search',json={'query':'router','mode':'semantic'})
                self.assertEqual(client.get('/ready?require_semantic=true').status_code,200)
                client.post('/search',json={'query':' '})
                client.get('/private-unmatched-identifier')
                client.post('/resolve',json={'complaint':'Private example@example.com router complaint'})
                result = client.get('/admin/metrics',headers={'X-API-Key':'editor'}).json()
                self.assertEqual(result['fallback_reasons']['generation_not_configured'],1)
                self.assertEqual(result['http_errors']['/search:422'],1)
                self.assertEqual(result['requests']['/unmatched'],1)
                self.assertNotIn('example@example.com',json.dumps(result))
                self.assertNotIn('private-unmatched-identifier',json.dumps(result))
