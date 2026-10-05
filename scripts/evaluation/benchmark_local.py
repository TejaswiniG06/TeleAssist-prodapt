"""Small in-process retrieval load measurement; no LLM calls or production claims."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time
from fastapi.testclient import TestClient
from teleassist.common.access import AccessPolicy
from teleassist.services.combined import create_app
from teleassist.common.monitoring import percentile


class NoProvider:
    configured = False


def run():
    app = create_app(cache_path=Path('runtime/embeddings.json'),provider=NoProvider(),
                     access=AccessPolicy(editor_key='local-benchmark-editor'))
    with TestClient(app) as client:
        start = time.perf_counter()
        first = client.post('/search',json={'query':'slow internet speed','mode':'hybrid'})
        first.raise_for_status()
        cold_ms = (time.perf_counter()-start)*1000
        reports = {}
        for mode in ('keyword','semantic','hybrid'):
            def search(number):
                query = ['slow internet speed','mobile calls fail','wifi drops repeatedly','iptv freezes'][number%4]
                started = time.perf_counter()
                response = client.post('/search',json={'query':query,'mode':mode})
                return {'milliseconds':(time.perf_counter()-started)*1000,'status':response.status_code}
            started = time.perf_counter()
            with ThreadPoolExecutor(max_workers=4) as workers:
                rows = list(workers.map(search,range(24)))
            seconds = time.perf_counter()-started
            latencies = [r['milliseconds'] for r in rows]
            reports[mode] = {'requests':len(rows),'concurrency':4,'errors':sum(r['status']!=200 for r in rows),
                             'p50_ms':round(percentile(latencies,.5),2),'p95_ms':round(percentile(latencies,.95),2),
                             'requests_per_second':round(len(rows)/seconds,2)}
        report = {'measurement':'FastAPI TestClient in-process, existing local model cache, no generation',
                  'active_sources':client.get('/health').json()['active_sources'],
                  'first_hybrid_ms':round(cold_ms,2),'modes':reports,
                  'metrics':client.get('/admin/metrics',headers={'X-API-Key':'local-benchmark-editor'}).json(),
                  'limitation':'Small local run; not network latency, production capacity or answer quality.'}
    Path('runtime').mkdir(exist_ok=True)
    Path('runtime/local-load-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    run()
