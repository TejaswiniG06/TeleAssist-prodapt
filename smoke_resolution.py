"""Live free-provider integration check; contains synthetic inputs only."""
import json
from pathlib import Path
from fastapi.testclient import TestClient
from api import create_app
from llm import FreeLLM, ProviderUnavailable


CASES = [
    {'complaint': 'My Wi-Fi disconnects every evening. I rebooted the router twice and it still happens. Contact me at demo@example.com.',
     'observations': 'All Wi-Fi devices drop, but an existing wired connection stays connected. The router is inside a cupboard. I can safely move it following the equipment instructions.'},
    {'complaint': 'My broadband internet is slow and videos keep buffering.',
     'observations': 'I have not yet compared an existing wired connection. Device scope and speed measurements are unknown.'},
    {'complaint': 'My mobile phone cannot make calls. It also shows no signal.',
     'observations': 'Other phones on the same provider at this location also have no signal. The issue started this morning.'},
]


def run():
    results = []
    class SyntheticTraceProvider(FreeLLM):
        sequence = 0
        def generate(self, *args, **kwargs):
            try:
                result = super().generate(*args, **kwargs)
            except ProviderUnavailable as error:
                print(json.dumps({'provider_error': str(error)}), flush=True)
                raise
            self.sequence += 1
            Path(f'runtime/synthetic-smoke-output-{self.sequence}.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
            return result
    with TestClient(create_app(cache_path=Path('runtime/embeddings.json'), provider=SyntheticTraceProvider())) as client:
        for case in CASES:
            response = client.post('/resolve', json=case)
            response.raise_for_status()
            result = response.json()
            assert 'demo@example.com' not in response.text
            assert result['generation'] == 'llm', result.get('reason')
            for step in result['steps']:
                source = client.get('/sources/' + step['source_id'])
                assert source.status_code == 200
                assert source.json()['version'] == step['source_version']
                assert step['action_id'] != 'restart_router'
            results.append(result)
    Path('runtime/resolve-smoke-report.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(json.dumps([{'status': r['status'], 'category': r['classification']['category'],
                       'steps': len(r['steps']), 'citations': [s['id'] for s in r['citations']],
                       'citation_check': r['citation_check']} for r in results], indent=2))


if __name__ == '__main__':
    run()
