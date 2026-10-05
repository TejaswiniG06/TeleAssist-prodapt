import hashlib
import json
from pathlib import Path
import unittest
from scripts.evaluation.evaluate_human_language import (BaselineProvider, FixedClassificationResolver,
    NO_REPEAT, repetition, repetition_summary, feature_summary)
from teleassist.resolution.pipeline import Classification


class HumanEvaluationTests(unittest.TestCase):
    def test_expected_abstention_is_not_scored_as_provider_failure(self):
        row={'checks':{'product':True,'category':True,'churn':True,'abstention':True},
             'classification_error':False,'ours':{'reason':'no_applicable_evidence'}}
        self.assertEqual(feature_summary([row],1)['all_requested_checks']['passed_cases'],1)
        row['ours']['reason']='provider_unavailable'
        self.assertEqual(feature_summary([row],1)['all_requested_checks']['passed_cases'],0)
    def test_challenge_set_frozen_before_scoring(self):
        suite=json.loads(Path('data/human_language_v1.json').read_text())
        self.assertEqual(len(suite['hard_queries']),10)
        self.assertEqual(len({c['id'] for c in suite['hard_queries']}),10)
        self.assertEqual(len(suite['feature_cases']),8)
        digest=hashlib.sha256(json.dumps(suite,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        self.assertEqual(digest,'1ea81c5ebe52503a470f028a242e275f8deb141a67c020b305f2de4ae9df0935',
                         'Publish a new version for label/query changes after scoring.')

    def test_no_step_answers_do_not_hide_repetition_denominator(self):
        outcome=lambda steps,repeat:{'step_count':steps,'repeated':repeat,'reason':None}
        rows=[{'ours':outcome(0,False)},{'ours':outcome(1,True)}]
        summary=repetition_summary(rows,'ours')
        self.assertEqual(summary['repeated_fix_rate'],.5)
        self.assertEqual(summary['repetition_among_answers_with_steps'],1)
        self.assertEqual(summary['answers_with_steps'],1)
        self.assertIsNone(repetition_summary([{'ours':outcome(0,False)}],'ours')['repetition_among_answers_with_steps'])

    def test_wording_grader_catches_opaque_ids(self):
        result={'steps':[{'action_id':'ACT_999','instruction':'Move the router to an open location.'}]}
        self.assertTrue(repetition(result,['move_router'])['repeated'])
        self.assertFalse(repetition(result,['restart_router'])['repeated'])

    def test_matched_baseline_removes_only_attempt_protection(self):
        class Provider:
            configured=True
            def generate(self,system,payload,max_tokens=4000):
                self.system,self.payload=system,payload
                return {'status':'resolution','steps':[{'source_id':'KB-X','source_version':1,
                    'action_id':'move_router','support_quote':'Move the router to an open location.',
                    'applicability_evidence':'router can be moved safely'}],'questions':[]}
        provider=Provider()
        record={'id':'KB-X','version':1,'record_type':'article','product':'broadband','evidence_tier':'kb',
                'steps':[{'action_id':'move_router','instruction':'Move the router to an open location.',
                          'condition':'Can be moved safely.'}]}
        hits=[{'id':'KB-X','version':1,'score':1,'record':record}]
        context='I moved the router but it did not help. The router can be moved safely.'
        classification=Classification(product='broadband',attempted_actions=[{'action_id':'move_router',
            'outcome':'failed','evidence':'I moved the router but it did not help.'}])
        ours=FixedClassificationResolver(lambda q,e:hits,provider,classification=classification)
        baseline=FixedClassificationResolver(lambda q,e:hits,BaselineProvider(provider),
                                             classification=classification,protect_attempts=False)
        self.assertEqual(ours.resolve(context)['steps'],[])
        result=baseline.resolve(context)
        self.assertTrue(repetition(result,['move_router'])['repeated'])
        self.assertEqual(result['citation_check'],'passed')
        self.assertNotIn(NO_REPEAT,provider.system)
        self.assertIn('Prefer relevant KB and resolved historical tickets',provider.system)
        self.assertEqual(provider.payload['classification']['attempted_actions'],[])
        self.assertTrue(classification.attempted_actions)
