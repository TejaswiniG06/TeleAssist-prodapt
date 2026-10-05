import json
import hashlib
from pathlib import Path
import unittest
from scripts.evaluation.evaluate_benchmark import reference_metrics
from scripts.evaluation.evaluate_public import near_duplicate_ids


class EvaluationTests(unittest.TestCase):
    def test_public_near_duplicate_exclusion(self):
        query='The router drops every evening and all devices lose their connection at home.'
        records=[{'id':'self','complaint':query},{'id':'near','complaint':query+' Please help.'},
                 {'id':'other','complaint':'Mobile roaming data does not work abroad.'}]
        self.assertEqual(near_duplicate_ids(query,records),['self','near'])

    def test_reference_metrics_penalize_misses_and_respect_cutoff(self):
        result=reference_metrics(['other','a','a','b','other','c'],['a','b','c'])
        self.assertEqual(result['reference_hit_at_5'],1)
        self.assertAlmostEqual(result['partial_reference_recall_at_5'],2/3)
        self.assertEqual(result['reference_reciprocal_rank_at_5'],.5)
        self.assertEqual(reference_metrics(['other'],['a'])['reference_reciprocal_rank_at_5'],0)

    def test_frozen_case_ids_and_reference_labels_exist(self):
        benchmark=json.loads(Path('data/benchmark_v1.json').read_text())
        cases=benchmark['cases']
        self.assertEqual(len({case['id'] for case in cases}),24)
        self.assertTrue(all(case['references'] for case in cases))
        self.assertEqual({case['product'] for case in cases},{'broadband','mobile','fixed_voice','iptv'})
        self.assertIn('independent human review pending',benchmark['label_origin'])
        digest=hashlib.sha256(json.dumps(benchmark,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        self.assertEqual(digest,'aa5404f75084650e10272ddfbb69a93c9775ca532223fc523d4bf7d462bf4985',
                         'Keep pilot-v1 frozen; change benchmark version when changing cases or labels.')
