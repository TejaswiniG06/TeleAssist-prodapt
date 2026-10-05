"""Add/search/retire a distinctive synthetic article with the real local model."""
import json
from pathlib import Path
import tempfile
import time
from fastapi.testclient import TestClient
from teleassist.common.access import AccessPolicy
from teleassist.services.combined import create_app
from teleassist.ingestion.catalog import EvidenceRecord


class NoProvider:
    configured=False


def wait_job(client, job_id, headers):
    deadline=time.monotonic()+120
    while time.monotonic()<deadline:
        result=client.get('/admin/jobs/'+job_id,headers=headers)
        result.raise_for_status()
        job=result.json()
        if job['status'] in ('published','failed'):
            assert job['status']=='published',job
            return job
        time.sleep(.1)
    raise RuntimeError('Indexing did not finish within the smoke-check budget.')


def run():
    base={'id':'KB-BASE','title':'Broadband observations','record_type':'article','product':'broadband',
          'category':'no_connection','provenance':'synthetic_demo','applicability':'Connection unavailable.',
          'steps':[{'action_id':'collect_indicator','instruction':'Collect the visible connection indicator state.',
                    'condition':'Customer can safely observe the equipment.'}]}
    article={**base,'id':'KB-E901','title':'Error E-901 on fiber ONT (synthetic test)',
             'applicability':'Customer reports Error E-901 on the ONT; cause is unverified.',
             'steps':[{'action_id':'collect_e901','instruction':'Record the displayed Error E-901 and refer it to authorized support.',
                       'condition':'Customer can safely read the displayed error.'}]}
    with tempfile.TemporaryDirectory() as folder:
        path=Path(folder)/'base.json'
        path.write_text(json.dumps([EvidenceRecord(**base).versioned(1)]),encoding='utf-8')
        app=create_app(path,cache_path=Path(folder)/'embeddings.json',state_path=Path(folder)/'state.json',
                       provider=NoProvider(),access=AccessPolicy(editor_key='temporary-smoke-editor'))
        with TestClient(app) as client:
            headers={'X-API-Key':'temporary-smoke-editor'}
            before=client.post('/search',json={'query':'E-901','mode':'keyword'}).json()['results']
            assert not before
            accepted=client.post('/admin/ingest',headers=headers,json={'expected_index_version':1,
                         'changes':[{'expected_version':0,'record':article}]})
            accepted.raise_for_status()
            added=wait_job(client,accepted.json()['id'],headers)
            result=client.post('/search',json={'query':'Error E-901 on fiber ONT','mode':'keyword'}).json()['results']
            assert result[0]['id']=='KB-E901'
            hybrid=client.post('/search',json={'query':'Error E-901 on fiber ONT','mode':'hybrid'}).json()['results']
            assert hybrid[0]['id']=='KB-E901'
            article['status']='retired'
            accepted=client.post('/admin/ingest',headers=headers,json={'expected_index_version':2,
                         'changes':[{'expected_version':1,'record':article}]})
            accepted.raise_for_status()
            retired=wait_job(client,accepted.json()['id'],headers)
            for mode in ('keyword','semantic','hybrid'):
                hits=client.post('/search',json={'query':'Error E-901 on fiber ONT','mode':mode}).json()['results']
                assert all(hit['id']!='KB-E901' for hit in hits)
            assert client.get('/sources/KB-E901?version=1').json()['status']=='active'
            report={'article_added_without_restart':True,'exact_error_keyword_match':True,
                    'hybrid_match':True,'retired_from_all_search_modes':True,
                    'historical_version_still_inspectable':True,'added_index_version':added['index_version'],
                    'retired_index_version':retired['index_version'],
                    'notice':'Real local model; isolated temporary catalog; fictional E-901, not provider-approved guidance.'}
    Path('runtime/evolving-data-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__': run()
