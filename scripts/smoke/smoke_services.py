"""Real-model integration check, separate from deterministic unit tests."""
import json
from pathlib import Path
from fastapi.testclient import TestClient
from teleassist.services.combined import create_app
from teleassist.retrieval.keyword import DATA


def main():
    app = create_app(cache_path=Path('runtime/embeddings.json'))
    report = {}
    with TestClient(app) as client:
        for mode in ('keyword', 'semantic', 'hybrid'):
            # Verify the original broadband KB example within its intended source pool.
            # The full mixed corpus can legitimately rank similar mobile history first.
            response = client.post('/search', json={'query': 'My internet crawls and videos keep stalling',
                                                   'mode': mode, 'product': 'broadband', 'record_type': 'article'})
            if response.status_code != 200:
                raise RuntimeError(response.text)
            ids = [r['id'] for r in response.json()['results']]
            report[mode] = ids
            if mode != 'keyword' and 'KB-002' not in ids:
                raise AssertionError(f'Slow speed evidence missing: {mode}: {ids}')
        response = client.post('/search', json={'query': 'cellular internet stopped', 'product': 'mobile',
                                               'record_type': 'article'})
        assert response.status_code == 200, response.text
        assert 'KB-005' in [r['id'] for r in response.json()['results']]
        report['health'] = client.get('/health').json()
        assert report['health']['semantic_ready']
        assert client.get('/sources/KB-005').status_code == 200
    Path('runtime/smoke-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
