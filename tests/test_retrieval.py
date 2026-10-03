import unittest
from retrieval import KeywordIndex, load_index


class RetrievalTests(unittest.TestCase):
    def test_retired_guidance_is_excluded(self):
        records = [dict(id='old', title='router', status='retired', version=1),
                   dict(id='new', title='router', status='active', version=2)]
        self.assertEqual([r['id'] for r in KeywordIndex(records).search('router')], ['new'])

    def test_no_overlap_returns_no_sources(self):
        self.assertEqual(load_index().search('xyzzynonexistent'), [])

    def test_slow_speed_retrieves_relevant_article(self):
        results = load_index().search('slow speed buffering', limit=2)
        self.assertIn('KB-002', [r['id'] for r in results])

    def test_invalid_input(self):
        with self.assertRaises(ValueError):
            load_index().search(' ')


if __name__ == '__main__':
    unittest.main()
