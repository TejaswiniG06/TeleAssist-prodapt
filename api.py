"""Retrieval and drafting API with explicit local/required access modes."""
from contextlib import asynccontextmanager
from collections import Counter
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from retrieval import DATA, KeywordIndex
from semantic import SemanticIndex, HybridIndex
from evidence import load_records
from resolution import Resolver
from privacy import mask
from access import AccessPolicy
from catalog import Catalog, IngestRequest, Conflict
from monitoring import Metrics, install_monitoring
from topics import TopicMonitor, TopicReview, ReplayRequest


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    mode: Literal['keyword', 'semantic', 'hybrid'] = 'hybrid'
    limit: int = Field(default=4, ge=1, le=20)
    min_semantic_score: float = Field(default=0.30, ge=0, le=1)
    product: str | None = None
    record_type: Literal['article', 'resolved_ticket', 'unverified_ticket', 'unresolved_ticket'] | None = None
    exclude_source_ids: list[str] = Field(default_factory=list, max_length=50)

    expected_index_version: int | None = Field(default=None, ge=1)

    @field_validator('query')
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError('Query must not be blank.')
        return value


class ResolveRequest(BaseModel):
    complaint: str = Field(min_length=1, max_length=5000)
    observations: str = Field(default='', max_length=3000)
    exclude_source_ids: list[str] = Field(default_factory=list, max_length=50)

    @field_validator('complaint')
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError('Complaint must not be blank.')
        return value


def create_app(data_path=DATA, encoder=None, cache_path=None, provider=None, include_public=None, access=None, state_path=None, topic_path=None):
    state = {}

    @asynccontextmanager
    async def lifespan(app):
        records = load_records(data_path, include_public=Path(data_path) == DATA if include_public is None else include_public)
        state['catalog'] = Catalog(records, encoder, cache_path, state_path)
        state['topics'] = TopicMonitor({r.get('category','unknown') for r in records},topic_path)
        try:
            yield
        finally:
            state['catalog'].close()

    app = FastAPI(title='PS2 evidence retrieval', lifespan=lifespan)
    metrics = Metrics()
    install_monitoring(app,metrics)
    def resolution_search(query, exclusions):
        hits = []
        snapshot = state['catalog'].current
        # Separate pools prevent a large public tier from crowding out KB/history.
        for kind in ('article', 'resolved_ticket', 'unverified_ticket', 'unresolved_ticket'):
            pool = perform_search(SearchRequest(query=query[:2000], mode='hybrid', limit=20,
                                               record_type=kind, min_semantic_score=0.32,
                                               exclude_source_ids=exclusions), snapshot)
            hits.extend(h for h in pool if h.get('components', {}).get('semantic', {}).get('score', 0) >= 0.32)
        return hits

    resolver = Resolver(resolution_search, provider, categories=lambda:state['topics'].taxonomy())
    access = access or AccessPolicy.from_environment()

    @app.get('/admin/access')
    def editor_access(role=Depends(access.editor)):
        return {'role': role, 'authentication_mode': access.mode}

    @app.post('/admin/ingest', status_code=202)
    def ingest(request: IngestRequest, role=Depends(access.editor)):
        if any(change.record.category not in state['topics'].taxonomy() for change in request.changes):
            raise HTTPException(422,'New categories need topic review before ingestion.')
        try:
            return state['catalog'].submit(request, role)
        except Conflict as error:
            raise HTTPException(409, str(error)) from None

    @app.get('/admin/jobs/{job_id}')
    def job(job_id: str, role=Depends(access.editor)):
        result = state['catalog'].job(job_id)
        if result is None:
            raise HTTPException(404, 'Job not found.')
        return result

    @app.get('/admin/audit')
    def audit(role=Depends(access.editor)):
        with state['catalog'].lock:
            return {'entries': list(state['catalog'].audit)}

    @app.get('/admin/metrics')
    def monitoring(role=Depends(access.editor)):
        result = metrics.snapshot()
        catalog = state['catalog']
        with catalog.lock:
            result['ingestion_jobs'] = dict(Counter(job['status'] for job in catalog.jobs.values()))
            result['index_version'] = catalog.current.version
        return result

    @app.get('/admin/topics')
    def topics(role=Depends(access.editor)):
        return state['topics'].report()

    @app.get('/taxonomy')
    def taxonomy(role=Depends(access.agent)):
        return {'categories':state['topics'].taxonomy()}

    @app.post('/admin/topics/replay')
    def replay(request: ReplayRequest, role=Depends(access.editor)):
        if any(not text.strip() or len(text)>2000 for text in request.complaints):
            raise HTTPException(422, 'Each complaint must contain 1–2000 characters.')
        for text in request.complaints:
            perform_search(SearchRequest(query=text,mode='hybrid'))
        return state['topics'].report()

    @app.post('/admin/topics/{topic_id}/review')
    def review(topic_id: str, request: TopicReview, role=Depends(access.editor)):
        try:
            return state['topics'].review(topic_id,request,role)
        except KeyError:
            raise HTTPException(404, 'Topic not found; reload proposals.') from None
        except ValueError as error:
            raise HTTPException(409,str(error)) from None
        except OSError:
            raise HTTPException(503,'Review could not be persisted; taxonomy unchanged.') from None

    @app.get('/live')
    def live():
        return {'status':'alive'}

    @app.get('/ready')
    def ready(require_semantic: bool = False):
        snapshot = state['catalog'].current
        if require_semantic and (snapshot.semantic is None or snapshot.semantic_error):
            raise HTTPException(503, 'Semantic index is not ready; keyword search is available.')
        return {'status':'ready', 'index_version':snapshot.version, 'keyword_ready':True,
                'semantic_ready':snapshot.semantic is not None and not snapshot.semantic_error}

    @app.get('/', include_in_schema=False)
    def interface():
        return FileResponse(Path(__file__).parent / 'web' / 'index.html')

    @app.get('/health')
    def health():
        snapshot = state['catalog'].current
        return {'status': 'degraded' if snapshot.semantic_error else 'ok',
                'index_version':snapshot.version,
                'active_sources': len(snapshot.records), 'keyword_ready': True,
                'record_types': dict(Counter(r['record_type'] for r in snapshot.records)),
                'semantic_ready': snapshot.semantic is not None,
                'semantic_state': 'unavailable' if snapshot.semantic_error else
                                  ('ready' if snapshot.semantic else 'not_loaded'),
                'generation_configured': resolver.provider.configured}

    @app.get('/sources/{source_id}')
    def source(source_id: str, version: int | None = Query(default=None, ge=1), role=Depends(access.agent)):
        catalog = state['catalog']
        if version is not None:
            with catalog.lock:
                record = catalog.history.get(f'{source_id}:{version}')
        else:
            record = next((r for r in catalog.current.records if r['id'] == source_id), None)
        if record is None:
            raise HTTPException(404, 'Active source not found.')
        return record

    @app.post('/search')
    def search(request: SearchRequest, role=Depends(access.agent)):
        snapshot = state['catalog'].current
        hits = perform_search(request,snapshot)
        return {'mode': request.mode, 'index_version':snapshot.version, 'results': [dict(hit, source_url='/sources/' + hit['id'] + '?version=' + str(hit['version'])) for hit in hits],
                'evidence_notice': 'Evidence tiers distinguish synthetic KB/history and unverified public suggestions; similarity does not establish applicability.'}

    def perform_search(request, snapshot=None):
        snapshot = snapshot or state['catalog'].current
        if request.expected_index_version is not None and request.expected_index_version != snapshot.version:
            raise HTTPException(409,'Index version changed; retry with a consistent version.')
        query = mask(request.query)[0]
        selected = [r for r in snapshot.records
                    if (request.product is None or r['product'] == request.product)
                    and (request.record_type is None or r['record_type'] == request.record_type)
                    and r['id'] not in request.exclude_source_ids]
        if request.mode == 'keyword':
            hits = KeywordIndex(selected).search(query, request.limit)
        else:
            try:
                semantic = state['catalog'].semantic(snapshot)
                allowed_ids = {record['id'] for record in selected}
                index = semantic if request.mode == 'semantic' else HybridIndex(snapshot.keyword, semantic)
                hits = index.search(query, request.limit, request.min_semantic_score, allowed_ids)
            except Exception:
                snapshot.semantic_error = True
                raise HTTPException(503, 'Local embedding service unavailable; keyword search remains available.') from None
        # Novelty signals are recorded separately; search results never auto-create fixes.
        if request.mode == 'keyword':
            weak = not hits
        else:
            scores = [h.get('components',{}).get('semantic',{}).get('score',0)
                      if request.mode=='hybrid' else h['score'] for h in hits]
            weak = max(scores,default=0) < .40
        # Filtered/excluded searches can miss deliberately; do not treat that as novelty.
        if weak and request.min_semantic_score <= .30 and request.product is None and request.record_type is None and not request.exclude_source_ids:
            state['topics'].observe(query,snapshot.version,'weak_'+request.mode+'_match')
        return hits

    @app.post('/resolve')
    def resolve(request: ResolveRequest, role=Depends(access.agent)):
        try:
            result = resolver.resolve(request.complaint, request.observations, request.exclude_source_ids)
        except HTTPException as error:
            if error.status_code != 503:
                raise
            from resolution import local_classification
            complaint, counts = mask(request.complaint)
            observations, observation_counts = mask(request.observations)
            for name,count in observation_counts.items():
                counts[name] = counts.get(name,0) + count
            result = resolver.fallback(complaint, counts, local_classification(complaint+'\n'+observations), 'retrieval_unavailable')
        metrics.resolution(result)
        if result.get('reason') == 'no_applicable_evidence' and not request.exclude_source_ids:
            state['topics'].observe(result['masked_complaint'],state['catalog'].current.version,'no_applicable_evidence')
        return result

    return app


app = create_app(cache_path=Path(__file__).parent / 'runtime' / 'embeddings.json',
                 state_path=Path(__file__).parent / 'runtime' / 'evidence_state.json',
                 topic_path=Path(__file__).parent / 'runtime' / 'topic_state.json')
