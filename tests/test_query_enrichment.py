import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from teleassist.services.combined import create_app
from teleassist.resolution.pipeline import Resolver
from teleassist.retrieval.query import build_search_query


class QueryEnrichmentTests(unittest.TestCase):
    def test_committed_predictions_replay_without_provider_calls(self):
        from scripts.evaluation.evaluate_query_enrichment import classify_queries, query_sets
        with patch('scripts.evaluation.evaluate_query_enrichment.FreeLLM',side_effect=AssertionError('Unexpected provider initialization')):
            cache,calls=classify_queries(query_sets())
        self.assertEqual(calls,0)
        self.assertEqual(len(cache['rows']),34)
    def test_raw_is_unchanged_and_metadata_is_bounded_and_masked(self):
        prediction={'product':'mobile','category':'mobile_data','symptoms':['pages fail','pages fail','call demo@example.com'],
                    'attempted_actions':[{'action_id':'toggle_airplane_mode'}],'severity':'critical','sentiment':'negative'}
        raw='My fone pages dont load; email demo@example.com.'
        self.assertEqual(build_search_query(raw,prediction,'raw'),'My fone pages dont load; email [EMAIL].')
        enriched=build_search_query(raw,prediction)
        self.assertIn('mobile data',enriched)
        self.assertIn('toggle airplane mode',enriched)
        self.assertEqual(enriched.count('pages fail'),1)
        self.assertNotIn('demo@example.com',enriched)
        self.assertNotIn('critical',enriched)
        self.assertEqual(build_search_query('plain',{'product':'unknown','category':'unknown'}),'plain')
        self.assertLessEqual(len(build_search_query('x'*5000,prediction)),2000)

    def test_resolve_reuses_classification_and_preserves_grounding_context(self):
        class Provider:
            configured=True
            def __init__(self): self.payloads=[]
            def generate(self,system,payload,max_tokens=4000):
                self.payloads.append(payload)
                if 'text' in payload:
                    return {'product':'broadband','category':'no_connection','symptoms':['router has no power'],'attempted_actions':[]}
                return {'status':'resolution','steps':[{'source_id':'KB-X','source_version':1,'action_id':'inspect',
                    'support_quote':'Inspect the equipment indicator.',
                    'applicability_evidence':'router has no power'}],'questions':[]}
        record={'id':'KB-X','version':1,'product':'broadband','record_type':'article','evidence_tier':'kb',
                'steps':[{'action_id':'inspect','instruction':'Inspect the equipment indicator.','condition':'Customer can observe the equipment.'}]}
        for mode in ('raw','enriched'):
            provider=Provider();queries=[]
            def search(query, exclusions):
                queries.append(query)
                return [{'id':'KB-X','version':1,'score':1,'record':record}]
            result=Resolver(search,provider).resolve('the little box is dark',query_mode=mode)
            self.assertEqual(len(provider.payloads),2)  # Existing classification + drafting only.
            self.assertEqual(provider.payloads[1]['customer_text'],'the little box is dark')
            self.assertEqual(result['reason'],'grounding_validation_failed')  # Enrichment cannot establish applicability.
            self.assertEqual(queries[0]=='the little box is dark',mode=='raw')

    def test_search_never_calls_provider_and_raw_does_not_use_prediction(self):
        class Provider:
            configured=True
            def generate(self,*args,**kwargs): raise AssertionError('Search must not call the provider')
        records=[{'id':'mobile','version':1,'status':'active','title':'mobile data airplane mode','product':'mobile','record_type':'article'}]
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'records.json';path.write_text(json.dumps(records))
            with TestClient(create_app(path,provider=Provider(),include_public=False)) as client:
                plain=client.post('/search',json={'query':'fone','mode':'keyword'}).json()
                raw=client.post('/search',json={'query':'fone','mode':'keyword','query_mode':'raw','classification':{'product':'mobile'}}).json()
                self.assertEqual(plain['results'],raw['results'])
                enriched=client.post('/search',json={'query':'fone','mode':'keyword','query_mode':'enriched','classification':{'product':'mobile'}}).json()
                self.assertEqual(enriched['results'][0]['id'],'mobile')
                self.assertEqual(client.post('/search',json={'query':'fone','query_mode':'enriched'}).status_code,422)
