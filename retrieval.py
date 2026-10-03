"""Inspectable BM25 baseline. Semantic retrieval will be added separately."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import re

DATA = Path(__file__).parent / 'data' / 'knowledge_base.json'


def tokens(text):
    return re.findall(r'[a-z0-9]+', text.lower())


def searchable_text(record):
    # Exclude IDs, provenance, versions, and other administrative metadata.
    fields = ['title', 'category', 'product', 'symptoms', 'steps', 'escalation',
              'complaint', 'observations', 'resolution_steps', 'suggested_steps', 'outcome', 'applicability']
    def flatten(value):
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            return ' '.join(flatten(item) for item in value)
        if isinstance(value, dict):
            return ' '.join(flatten(v) for k, v in value.items() if k != 'action_id')
        return ''
    return ' '.join(flatten(record.get(field, '')) for field in fields)


class KeywordIndex:
    def __init__(self, records):
        self.records = [r for r in records if r['status'] == 'active']
        self.counts = [Counter(tokens(searchable_text(r))) for r in self.records]
        self.lengths = [sum(c.values()) for c in self.counts]
        self.average_length = sum(self.lengths) / max(1, len(self.lengths))
        self.document_frequency = Counter(t for c in self.counts for t in c)

    def search(self, query, limit=4):
        if not query.strip() or not 1 <= limit <= 20:
            raise ValueError('Query must be nonempty and limit between 1 and 20.')
        results = []
        for record, counts, length in zip(self.records, self.counts, self.lengths):
            score = 0.0
            for term in set(tokens(query)):
                frequency = counts.get(term, 0)
                if not frequency:
                    continue
                df = self.document_frequency[term]
                idf = math.log(1 + (len(self.records) - df + 0.5) / (df + 0.5))
                denominator = frequency + 1.5 * (0.25 + 0.75 * length / max(1, self.average_length))
                score += idf * frequency * 2.5 / denominator
            if score > 0:
                results.append({'id': record['id'], 'version': record['version'],
                                'score': round(score, 6), 'record': record})
        return sorted(results, key=lambda r: (-r['score'], r['id']))[:limit]


def load_index(path=DATA):
    records = json.loads(Path(path).read_text(encoding='utf-8'))
    ids = [r['id'] for r in records]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate source IDs.')
    return KeywordIndex(records)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('query')
    parser.add_argument('--limit', type=int, default=4)
    args = parser.parse_args()
    print(json.dumps(load_index().search(args.query, args.limit), indent=2))
