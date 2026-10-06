"""Standalone resolution service; retrieval is an explicit HTTP dependency."""
from teleassist.common.paths import PROJECT_ROOT
from contextlib import asynccontextmanager
import os
from urllib.parse import quote
import httpx
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from teleassist.common.access import AccessPolicy
from teleassist.services.schemas import ResolveRequest, SearchRequest
from teleassist.resolution.llm import FreeLLM, load_environment
from teleassist.common.monitoring import Metrics, install_monitoring
from teleassist.common.privacy import mask
from teleassist.resolution.pipeline import Resolver, local_classification


class RemoteEvidence:
    def __init__(self, url, key='', transport=None):
        self.client = httpx.Client(base_url=url,timeout=60,
                                   headers={'X-API-Key':key} if key else {},transport=transport)

    def request(self, method, path, payload=None):
        try:
            response = self.client.request(method,path,json=payload)
            if response.status_code == 404:
                raise HTTPException(404,'Evidence not found.')
            if response.status_code == 409:
                raise HTTPException(503,'Evidence changed during retrieval; retry the draft.')
            if response.status_code != 200:
                raise HTTPException(503,'Retrieval service unavailable or access rejected.')
            data=response.json()
            if not isinstance(data,dict):
                raise ValueError('Invalid retrieval response.')
            return data
        except (httpx.HTTPError,ValueError):
            raise HTTPException(503,'Retrieval service unavailable.') from None

    def categories(self):
        categories=self.request('GET','/taxonomy').get('categories')
        if not isinstance(categories,list) or not all(isinstance(label,str) for label in categories):
            raise HTTPException(503,'Retrieval taxonomy response is invalid.')
        return categories

    def search(self, query, exclusions):
        version = self.request('GET','/health')['index_version']
        hits=[]
        for kind in ('article','resolved_ticket','unverified_ticket','unresolved_ticket'):
            payload = {'query':mask(query[:2000])[0], 'mode':'hybrid','limit':20,'min_semantic_score':.32,
                       'record_type':kind,'exclude_source_ids':exclusions,'expected_index_version':version}
            results = self.request('POST','/search',payload)['results']
            hits.extend(h for h in results if h.get('components',{}).get('semantic',{}).get('score',0) >= .32)
        return hits

    def observe(self, complaint):
        # Topic monitoring is best effort; it must not replace a valid response with an outage.
        try:
            self.request('POST', '/topics/observations', {'complaint': complaint})
        except HTTPException:
            pass


def create_resolution_app(retrieval_url=None, retrieval_key=None, provider=None, access=None, transport=None):
    load_environment()
    remote = RemoteEvidence(retrieval_url or os.getenv('RETRIEVAL_URL','http://127.0.0.1:8001'),
                            retrieval_key if retrieval_key is not None else os.getenv('RETRIEVAL_API_KEY',''),transport)
    resolver = Resolver(remote.search,provider or FreeLLM(),categories=remote.categories)
    access = access or AccessPolicy.from_environment()
    metrics=Metrics()

    @asynccontextmanager
    async def lifespan(app):
        yield
        remote.client.close()

    app=FastAPI(title='TeleAssist resolution service',lifespan=lifespan)
    install_monitoring(app,metrics)

    @app.get('/',include_in_schema=False)
    def interface():
        return FileResponse(PROJECT_ROOT/'web/index.html')

    @app.get('/live')
    def live():
        return {'status':'alive'}

    @app.get('/health')
    def health():
        data=remote.request('GET','/health')
        return {**data,'service':'resolution','generation_configured':resolver.provider.configured}

    @app.get('/ready')
    def ready(require_semantic: bool=False):
        return remote.request('GET','/ready'+('?require_semantic=true' if require_semantic else ''))

    @app.post('/search')
    def search(request:SearchRequest,role=Depends(access.agent)):
        payload=request.model_dump(exclude_none=True)
        payload['query']=mask(payload['query'])[0]
        return remote.request('POST','/search',payload)

    @app.get('/sources/{source_id}')
    def source(source_id:str,version:int|None=Query(default=None,ge=1),role=Depends(access.agent)):
        path='/sources/'+quote(source_id,safe='')
        if version is not None:
            path+='?version='+str(version)
        return remote.request('GET',path)

    @app.get('/taxonomy')
    def taxonomy(role=Depends(access.agent)):
        return {'categories':remote.categories()}

    @app.get('/admin/metrics')
    def monitoring(role=Depends(access.editor)):
        return metrics.snapshot()

    @app.post('/resolve')
    def resolve(request:ResolveRequest,role=Depends(access.agent)):
        try:
            result=resolver.resolve(request.complaint,request.observations,request.exclude_source_ids,query_mode=request.query_mode)
        except HTTPException as error:
            if error.status_code != 503:
                raise
            complaint,counts=mask(request.complaint)
            observations,observation_counts=mask(request.observations)
            for name,count in observation_counts.items():
                counts[name]=counts.get(name,0)+count
            result=resolver.fallback(complaint,counts,local_classification(complaint+'\n'+observations),'retrieval_unavailable')
        metrics.resolution(result)
        if result.get('reason') == 'no_applicable_evidence' and not request.exclude_source_ids:
            remote.observe(result['masked_complaint'])
        result['query_mode']=request.query_mode
        return result

    return app


app=create_resolution_app()
