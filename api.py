"""Read-only retrieval API. Run locally until authentication is implemented."""
from contextlib import asynccontextmanager
from collections import Counter
from pathlib import Path
from threading import Lock
from typing import Literal
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from retrieval import DATA, KeywordIndex
from semantic import SemanticIndex, HybridIndex
from evidence import load_records
from resolution import Resolver
from privacy import mask


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    mode: Literal['keyword', 'semantic', 'hybrid'] = 'hybrid'
    limit: int = Field(default=4, ge=1, le=20)
    min_semantic_score: float = Field(default=0.30, ge=0, le=1)
    product: str | None = None
    record_type: Literal['article', 'resolved_ticket', 'unverified_ticket', 'unresolved_ticket'] | None = None
    exclude_source_ids: list[str] = Field(default_factory=list, max_length=50)

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


def create_app(data_path=DATA, encoder=None, cache_path=None, provider=None, include_public=None):
    state = {'semantic': None, 'semantic_error': False}
    lock = Lock()

    @asynccontextmanager
    async def lifespan(app):
        records = load_records(data_path, include_public=Path(data_path) == DATA if include_public is None else include_public)
        state['records'] = [r for r in records if r['status'] == 'active']
        state['keyword'] = KeywordIndex(state['records'])
        yield

    app = FastAPI(title='PS2 evidence retrieval', lifespan=lifespan)
    def resolution_search(query, exclusions):
        hits = []
        # Separate pools prevent a large public tier from crowding out KB/history.
        for kind in ('article', 'resolved_ticket', 'unverified_ticket', 'unresolved_ticket'):
            pool = perform_search(SearchRequest(query=query[:2000], mode='hybrid', limit=20,
                                               record_type=kind, min_semantic_score=0.32,
                                               exclude_source_ids=exclusions))
            hits.extend(h for h in pool if h.get('components', {}).get('semantic', {}).get('score', 0) >= 0.32)
        return hits

    resolver = Resolver(resolution_search, provider)

    @app.get('/', include_in_schema=False)
    def interface():
        return FileResponse(Path(__file__).parent / 'web' / 'index.html')

    @app.get('/health')
    def health():
        return {'status': 'degraded' if state['semantic_error'] else 'ok',
                'active_sources': len(state['records']), 'keyword_ready': True,
                'record_types': dict(Counter(r['record_type'] for r in state['records'])),
                'semantic_ready': state['semantic'] is not None,
                'semantic_state': 'unavailable' if state['semantic_error'] else
                                  ('ready' if state['semantic'] else 'not_loaded'),
                'generation_configured': resolver.provider.configured}

    @app.get('/sources/{source_id}')
    def source(source_id: str):
        record = next((r for r in state['records'] if r['id'] == source_id), None)
        if record is None:
            raise HTTPException(404, 'Active source not found.')
        return record

    @app.post('/search')
    def search(request: SearchRequest):
        hits = perform_search(request)
        return {'mode': request.mode, 'results': [dict(hit, source_url='/sources/' + hit['id']) for hit in hits],
                'evidence_notice': 'Evidence tiers distinguish synthetic KB/history and unverified public suggestions; similarity does not establish applicability.'}

    def perform_search(request):
        query = mask(request.query)[0]
        selected = [r for r in state['records']
                    if (request.product is None or r['product'] == request.product)
                    and (request.record_type is None or r['record_type'] == request.record_type)
                    and r['id'] not in request.exclude_source_ids]
        if request.mode == 'keyword':
            hits = KeywordIndex(selected).search(query, request.limit)
        else:
            with lock:
                try:
                    if state['semantic'] is None:
                        state['semantic'] = SemanticIndex(state['records'], encoder,
                                                         cache_path=cache_path)
                    semantic = state['semantic']
                    # Filter by ID before ranking; cached source embeddings remain unchanged.
                    allowed_ids = {record['id'] for record in selected}
                    index = semantic if request.mode == 'semantic' else HybridIndex(state['keyword'], semantic)
                    hits = index.search(query, request.limit, request.min_semantic_score, allowed_ids)
                    state['semantic_error'] = False
                except Exception:
                    state['semantic_error'] = True
                    raise HTTPException(503, 'Local embedding service unavailable; keyword search remains available.')
        return hits

    @app.post('/resolve')
    def resolve(request: ResolveRequest):
        try:
            return resolver.resolve(request.complaint, request.observations, request.exclude_source_ids)
        except HTTPException as error:
            if error.status_code != 503:
                raise
            from resolution import local_classification
            complaint, counts = mask(request.complaint)
            return resolver.fallback(complaint, counts, local_classification(complaint), 'retrieval_unavailable')

    return app


app = create_app(cache_path=Path(__file__).parent / 'runtime' / 'embeddings.json')
