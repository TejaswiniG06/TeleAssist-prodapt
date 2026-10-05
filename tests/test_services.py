import json
from pathlib import Path
import tempfile
import unittest
from fastapi.testclient import TestClient
from teleassist.services.combined import create_app
from teleassist.retrieval.semantic import SemanticIndex, HybridIndex
from teleassist.retrieval.keyword import KeywordIndex, searchable_text


class Encoder:
    def __init__(self):
        self.calls = []

    def encode(self, texts):
        self.calls.append(texts)
        return [[1, 0] if any(w in t.lower() for w in ('router', 'wireless')) else [0, 1] for t in texts]


def records():
    return [dict(id='a', version=1, status='active', title='router', product='broadband', record_type='article'),
            dict(id='b', version=1, status='active', title='mobile calls', product='mobile', record_type='article'),
            dict(id='old', version=1, status='retired', title='router', product='broadband', record_type='article')]


class ServicesTests(unittest.TestCase):
    def test_semantic_paraphrase_and_retired(self):
        index = SemanticIndex(records(), Encoder())
        self.assertEqual([r['id'] for r in index.search('wireless')], ['a'])
        self.assertEqual(index.search('wireless', min_score=1), index.search('wireless'))

    def test_incremental_cache_invalidation(self):
        with tempfile.TemporaryDirectory() as folder:
            cache = Path(folder) / 'cache.json'
            encoder = Encoder()
            SemanticIndex(records(), encoder, cache, 'test')
            SemanticIndex(records(), encoder, cache, 'test')
            self.assertEqual(len(encoder.calls), 1)
            changed = records()
            changed[0]['title'] = 'router new'
            SemanticIndex(changed, encoder, cache, 'test')
            self.assertEqual(encoder.calls[-1], [searchable_text(changed[0])])
            SemanticIndex(changed, encoder, cache, 'different-model')
            self.assertEqual(len(encoder.calls[-1]), 2)

    def test_hybrid_fusion_exposes_components(self):
        index = HybridIndex(KeywordIndex(records()), SemanticIndex(records(), Encoder()))
        result = index.search('router')[0]
        self.assertEqual(set(result['components']), {'keyword', 'semantic'})
        self.assertAlmostEqual(result['score'], 2 / 61)

    def test_filter_before_limit_without_reembedding_sources(self):
        # More excluded matches than the ranking pool: filtering after ranking
        # would incorrectly discard the only allowed match.
        corpus = [dict(records()[0], id=f'a{i:02}') for i in range(25)]
        encoder = Encoder()
        semantic = SemanticIndex(corpus, encoder)
        hybrid = HybridIndex(KeywordIndex(corpus), semantic)
        for index in (semantic, hybrid):
            hits = index.search('router', limit=1, allowed_ids={'a24'})
            self.assertEqual([hit['id'] for hit in hits], ['a24'])
            self.assertEqual(index.search('router', allowed_ids=set()), [])
        # Identical source text is encoded only once during construction.
        self.assertEqual(encoder.calls[0], [searchable_text(corpus[0])])
        self.assertTrue(all(call == ['router'] for call in encoder.calls[1:]))

    def test_api_validation_filters_and_citations(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'data.json'
            path.write_text(json.dumps(records()))
            with TestClient(create_app(path, Encoder())) as client:
                self.assertFalse(client.get('/health').json()['semantic_ready'])
                for mode in ('keyword', 'semantic', 'hybrid'):
                    response = client.post('/search', json={'query': 'router', 'mode': mode})
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json()['results'][0]['source_url'], '/sources/a?version=1')
                self.assertEqual(client.get('/sources/old').status_code, 404)
                self.assertEqual(client.get('/sources/a').status_code, 200)
                response = client.post('/search', json={'query': 'router', 'product': 'mobile'})
                self.assertEqual(response.json()['results'], [])
                for payload in ({'query': ' '}, {'query': 'router', 'limit': 21}, {'query': 'router', 'mode': 'invalid'}):
                    self.assertEqual(client.post('/search', json=payload).status_code, 422)

    def test_embedding_failure_does_not_break_keyword(self):
        class Broken:
            def encode(self, texts):
                raise RuntimeError('private diagnostic')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'data.json'
            path.write_text(json.dumps(records()))
            with TestClient(create_app(path, Broken())) as client:
                self.assertEqual(client.post('/search', json={'query': 'router'}).status_code, 503)
                self.assertEqual(client.get('/health').json()['status'], 'degraded')
                self.assertEqual(client.post('/search', json={'query': 'router', 'mode': 'keyword'}).status_code, 200)


if __name__ == '__main__':
    unittest.main()
