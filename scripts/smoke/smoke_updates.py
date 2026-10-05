"""Real local-model update check in temporary storage; no provider key needed."""
import json
from pathlib import Path
import tempfile
import time
from fastapi.testclient import TestClient
from teleassist.common.access import AccessPolicy
from teleassist.services.combined import create_app
from teleassist.ingestion.catalog import EvidenceRecord


class NoProvider:
    configured = False


def main():
    record = dict(id='DEMO-KB',title='Router power check',record_type='article',product='broadband',
                  category='no_connection',provenance='synthetic_demo',applicability='Router has no visible power indicators.',
                  steps=[dict(action_id='check_power',instruction='Ask whether the router power indicator is visible.',condition='Power state is unknown.')])
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder)/'records.json'
        path.write_text(json.dumps([EvidenceRecord(**record).versioned(1)]))
        app = create_app(path,cache_path=Path(folder)/'embeddings.json',state_path=Path(folder)/'state.json',
                         provider=NoProvider(),access=AccessPolicy(editor_key='local-editor-demo'))
        with TestClient(app) as client:
            headers = {'X-API-Key':'local-editor-demo'}
            record['title']='Updated router power check'
            response = client.post('/admin/ingest',headers=headers,json={'expected_index_version':1,
                'changes':[{'expected_version':1,'record':record}]})
            assert response.status_code == 202, response.text
            deadline = time.monotonic()+120
            while time.monotonic() < deadline:
                assert client.post('/search',json={'query':'router power','mode':'keyword'}).status_code == 200
                job = client.get('/admin/jobs/'+response.json()['id'],headers=headers).json()
                if job['status'] in ('published','failed'):
                    break
                time.sleep(.1)
            assert job['status'] == 'published', job
            result = client.post('/search',json={'query':'router power','mode':'hybrid'}).json()['results']
            assert result[0]['version'] == 2
            assert client.get('/sources/DEMO-KB?version=1').json()['version'] == 1
            print(json.dumps({'job':job,'hybrid_source_version':result[0]['version'],
                              'old_citation_version':1,'reader_checks':'passed','storage':'temporary'},indent=2))


if __name__ == '__main__':
    main()
