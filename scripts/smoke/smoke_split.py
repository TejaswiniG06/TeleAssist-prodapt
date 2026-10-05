"""Two real localhost HTTP processes; key-free draft fallback, no provider calls."""
from teleassist.common.paths import PROJECT_ROOT
import json
import os
from pathlib import Path
import socket
import subprocess
import shutil
import sys
import tempfile
import time
from uuid import uuid4
import httpx
from start import stop_process


def unused_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0))
        return sock.getsockname()[1]


def check_feedback(client, retrieval, gateway):
    """Fictional feedback and evidence mutations live only in the temporary catalog."""
    headers = {'X-API-Key':'smoke-editor'}
    def post(path, payload):
        response = client.post(retrieval + path, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    case = post('/cases', {'request_id':uuid4().hex, 'complaint':'Fictional SPLIT901 optical connector fault.',
        'draft':{'status':'clarification', 'answer':'Pending fictional technician review.',
                 'classification':{'product':'broadband','category':'no_connection'}}})
    assert not client.post(gateway+'/search', json={'query':'SPLIT901','mode':'keyword'}).json()['results']
    case = post('/cases/'+case['id']+'/outcome', {'expected_revision':case['revision'], 'outcome':'resolved',
        'actual_actions':['Technician replaced a damaged optical connector.'],
        'outcome_evidence':'Fictional customer confirmed stable connectivity after the replacement.', 'confirmed':True})
    version = client.get(retrieval+'/health').json()['index_version']
    post('/admin/cases/'+case['id']+'/review', {'expected_revision':case['revision'],
        'expected_index_version':version, 'decision':'approve', 'title':'Fictional SPLIT901 connector repair',
        'product':'broadband', 'category':'no_connection', 'applicability':'Technician confirms optical connector damage.',
        'rationale':'Isolated smoke verification with fictional outcome confirmation.', 'confirmed':True})
    deadline=time.monotonic()+120
    while time.monotonic()<deadline:
        case=client.get(retrieval+'/cases/'+case['id']).json()
        if case['status']!='publishing': break
        time.sleep(.1)
    assert case['status']=='published', case
    for mode in ('keyword','semantic','hybrid'):
        hits=client.post(gateway+'/search',json={'query':'Fictional SPLIT901 optical connector fault.',
            'mode':mode,'record_type':'resolved_ticket','limit':20}).json()['results']
        assert case['publication']['source_id'] in [hit['id'] for hit in hits], mode
    # Retirement removes current evidence while exact historical citations remain accessible.
    source=client.get(retrieval+'/sources/'+case['publication']['source_id']).json()
    source['status']='retired'
    # Only public EvidenceRecord fields belong in an ingestion request.
    from teleassist.ingestion.catalog import EvidenceRecord
    record=EvidenceRecord.model_validate({name:source[name] for name in EvidenceRecord.model_fields if name in source}).model_dump()
    job=post('/admin/ingest', {'expected_index_version':version+1,
        'changes':[{'expected_version':1,'record':record}]})
    deadline=time.monotonic()+120
    while time.monotonic()<deadline:
        job=client.get(retrieval+'/admin/jobs/'+job['id'],headers=headers).json()
        if job['status'] in ('published','failed'): break
        time.sleep(.1)
    assert job['status']=='published', job
    assert client.get(gateway+'/sources/'+source['id']).status_code==404
    assert client.get(gateway+'/sources/'+source['id']+'?version=1').status_code==200
    return case['id'], source['id']


def main():
    root=PROJECT_ROOT
    temporary=tempfile.TemporaryDirectory()
    state=Path(temporary.name)
    cache=root/'runtime'/'embeddings.json'
    if cache.exists(): shutil.copy2(cache,state/'embeddings.json')
    retrieval_port,resolution_port=unused_port(),unused_port()
    env={**os.environ,'AUTH_MODE':'local','LLM_FREE_PLAN_CONFIRMED':'false',
         'RETRIEVAL_URL':f'http://127.0.0.1:{retrieval_port}','RETRIEVAL_API_KEY':'',
         'HF_HUB_OFFLINE':'1','TELEASSIST_STATE_DIR':str(state),
         'TELEASSIST_AGENT_KEY':'smoke-agent','TELEASSIST_EDITOR_KEY':'smoke-editor'}
    children,logs=[],[]
    (root/'runtime').mkdir(exist_ok=True)
    try:
        for module,port in [('retrieval_api',retrieval_port),('resolution_api',resolution_port)]:
            log=(root/'runtime'/('smoke-'+module+'.log')).open('w',encoding='utf-8')
            logs.append(log)
            children.append(subprocess.Popen([sys.executable,'-m','uvicorn',module+':app','--host','127.0.0.1','--port',str(port)],
                            cwd=root,env=env,stdout=log,stderr=log,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0))
        with httpx.Client(timeout=120) as client:
            deadline=time.monotonic()+90
            while time.monotonic()<deadline:
                try:
                    if all(client.get(f'http://127.0.0.1:{port}/live').status_code==200 for port in (retrieval_port,resolution_port)):
                        break
                except httpx.HTTPError:
                    pass
                if any(child.poll() is not None for child in children):
                    raise RuntimeError('A service exited before becoming live.')
                time.sleep(.2)
            gateway=f'http://127.0.0.1:{resolution_port}'
            health=client.get(gateway+'/health'); health.raise_for_status()
            # Cache must already exist; warm retrieval directly before testing the gateway timeout budget.
            warm=client.post(f'http://127.0.0.1:{retrieval_port}/search',json={'query':'slow broadband speed','mode':'hybrid'})
            warm.raise_for_status()
            result=client.post(gateway+'/search',json={'query':'slow broadband speed','mode':'hybrid'})
            result.raise_for_status()
            hit=result.json()['results'][0]
            source=client.get(gateway+'/sources/'+hit['id']+'?version='+str(hit['version']))
            source.raise_for_status()
            draft=client.post(gateway+'/resolve',json={'complaint':'My router is offline; email example@example.com.'})
            draft.raise_for_status()
            assert draft.json()['reason']=='generation_not_configured'
            assert 'example@example.com' not in draft.text
            assert client.post(f'http://127.0.0.1:{retrieval_port}/resolve',json={'complaint':'test'}).status_code==404
            case_id,source_id=check_feedback(client,f'http://127.0.0.1:{retrieval_port}',gateway)
            # Stop only the child started by this smoke test, then inspect dependency failure.
            stop_process(children[0])
            unavailable=client.post(gateway+'/resolve',json={'complaint':'My router is offline.'})
            assert unavailable.json()['reason']=='retrieval_unavailable'
            print(json.dumps({'transport':'two real localhost HTTP processes',
                              'sources':health.json()['active_sources'],'hybrid_hit':hit['id'],
                              'versioned_source':'passed','key_free_fallback':'passed','retrieval_outage':'passed',
                              'case_outcome_publication':'passed','future_search_all_modes':'passed',
                              'retirement_and_historical_citation':'passed','storage':'isolated temporary'},indent=2))
    finally:
        for child in children:
            stop_process(child)
        for log in logs:
            log.close()
        temporary.cleanup()


if __name__=='__main__':
    main()
