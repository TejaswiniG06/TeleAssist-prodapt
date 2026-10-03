"""Two real localhost HTTP processes; key-free draft fallback, no provider calls."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import httpx


def unused_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0))
        return sock.getsockname()[1]


def main():
    root=Path(__file__).parent
    retrieval_port,resolution_port=unused_port(),unused_port()
    env={**os.environ,'AUTH_MODE':'local','LLM_FREE_PLAN_CONFIRMED':'false',
         'RETRIEVAL_URL':f'http://127.0.0.1:{retrieval_port}','RETRIEVAL_API_KEY':'',
         'HF_HUB_OFFLINE':'1'}
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
            # Stop only the child started by this smoke test, then inspect dependency failure.
            children[0].terminate(); children[0].wait(timeout=10)
            unavailable=client.post(gateway+'/resolve',json={'complaint':'My router is offline.'})
            assert unavailable.json()['reason']=='retrieval_unavailable'
            print(json.dumps({'transport':'two real localhost HTTP processes',
                              'sources':health.json()['active_sources'],'hybrid_hit':hit['id'],
                              'versioned_source':'passed','key_free_fallback':'passed','retrieval_outage':'passed'},indent=2))
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill(); child.wait(timeout=10)
        for log in logs:
            log.close()


if __name__=='__main__':
    main()
