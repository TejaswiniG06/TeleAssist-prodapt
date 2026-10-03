import json
from pathlib import Path
import tempfile
import unittest
from evidence import public_records, build_public_evaluation
from generate_corpus import Article, validate_batch


class CorpusTests(unittest.TestCase):
    def test_unverified_ingestion_keeps_reply_and_provenance(self):
        candidate = {'source_row': 12, 'subject': 'Router trouble', 'body': 'Contact user@example.com. Router drops.',
                     'answer': 'Compare wired and wireless connections.', 'source_labels': {'priority': 'high'},
                     'source_url': 'https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets',
                     'creator': 'Tobi-Bueck / Softoft', 'license': 'CC-BY-NC-4.0'}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'candidates.json'
            path.write_text(json.dumps([candidate]))
            record = public_records(path)[0]
            self.assertEqual(record['evidence_tier'], 'unverified')
            self.assertEqual(record['outcome'], 'unknown')
            self.assertEqual(record['suggested_steps'], candidate['answer'])
            self.assertNotIn('user@example.com', record['complaint'])
            self.assertEqual(record['license'], 'CC-BY-NC-4.0')
            cases = build_public_evaluation([record], Path(folder) / 'eval.json')
            self.assertEqual(cases[0]['excluded_source_id'], record['id'])
            self.assertEqual(cases[0]['annotation_status'], 'pending_manual_relevance_review')

    def test_short_or_pii_batch_rejected(self):
        item = {'title': 'Router triage', 'product': 'broadband', 'category': 'no_connection',
                'symptoms': ['offline', 'all devices disconnected'],
                'steps': [{'action_id': 'check_device_scope', 'instruction': 'Ask which devices are affected.',
                           'condition': 'Device scope is unknown.'}], 'escalation': 'Refer to authorized support.'}
        with self.assertRaises(ValueError):
            validate_batch([item], Article, 2)
        item['title'] = 'Email customer@example.com'
        with self.assertRaises(ValueError):
            validate_batch([item], Article, 1)
