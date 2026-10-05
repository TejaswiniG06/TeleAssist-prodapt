"""Query-only public evaluation; self matches excluded, labels reviewed separately."""
import argparse
import json
from pathlib import Path
from fastapi.testclient import TestClient
from teleassist.services.combined import create_app
from teleassist.retrieval.evidence import build_public_evaluation, public_records
from teleassist.common.privacy import mask
from teleassist.retrieval.keyword import tokens


def near_duplicate_ids(query, records, threshold=.80):
    def shingles(text):
        words=tokens(mask(text)[0])
        return {tuple(words[i:i+3]) for i in range(max(0,len(words)-2))}
    target=shingles(query)
    result=[]
    for record in records:
        candidate=shingles(record.get('complaint',''))
        if query==record.get('complaint') or (target and candidate and len(target&candidate)/len(target|candidate)>=threshold):
            result.append(record['id'])
    return result


def run(resolve=False):
    path = Path('data/public_evaluation.json')
    if not path.exists():
        build_public_evaluation(public_records())
    cases = json.loads(path.read_text(encoding='utf-8'))
    report = []
    indexed_public = public_records()
    with TestClient(create_app(cache_path=Path('runtime/embeddings.json'))) as client:
        for case in cases:
            row = {'id': case['id'], 'annotation_status': case['annotation_status']}
            exclusions = sorted(set(near_duplicate_ids(case['query'],indexed_public)+[case['excluded_source_id']]))
            if len(exclusions)>50:
                raise ValueError('More than 50 near duplicates; review the candidate corpus before evaluating.')
            row['excluded_source_ids'] = exclusions
            row['near_duplicate_threshold'] = .80
            for mode in ('keyword', 'semantic', 'hybrid'):
                response = client.post('/search', json={'query': case['query'][:2000], 'mode': mode,
                                                        'exclude_source_ids': exclusions})
                response.raise_for_status()
                row[mode] = [r['id'] for r in response.json()['results']]
                assert not set(exclusions).intersection(row[mode])
            if resolve:
                response = client.post('/resolve', json={'complaint': case['query'][:5000],
                                                         'exclude_source_ids': exclusions})
                response.raise_for_status()
                row['resolution'] = response.json()
            report.append(row)
    Path('runtime').mkdir(exist_ok=True)
    Path('runtime/public-evaluation-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'cases': len(report), 'self_match_exclusion': 'passed',
                      'quality_metrics': 'pending manual relevance labels', 'generation_evaluated': resolve}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--resolve', action='store_true')
    args = parser.parse_args()
    run(args.resolve)
