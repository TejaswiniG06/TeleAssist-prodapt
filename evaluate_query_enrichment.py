"""Paired raw/enriched retrieval; one shared classification per frozen query."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from fastapi.testclient import TestClient
from access import AccessPolicy
from api import create_app
from evaluate_benchmark import NoProvider, reference_metrics
from evidence import load_records
from llm import FreeLLM, ProviderUnavailable
from resolution import Resolver, Classification, local_classification
from retrieval import DATA
from retrieval_query import build_search_query


ROOT=Path(__file__).parent
CACHE=ROOT/'data/query_classifications_v1.json'
RESULT=ROOT/'data/query_enrichment_results_v1.json'


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def query_sets():
    pilot=json.loads((ROOT/'data/benchmark_v1.json').read_text(encoding='utf-8'))
    human=json.loads((ROOT/'data/human_language_v1.json').read_text(encoding='utf-8'))
    return {'pilot_24':pilot['cases'],'hard_10':human['hard_queries']}


def classify_queries(sets, refresh=False):
    categories=sorted({r.get('category','unknown') for r in load_records(DATA)}|{'unknown'})
    # Normalize Git line endings so a Windows reviewer can replay the cache.
    code_hash=hashlib.sha256((ROOT/'resolution.py').read_text(encoding='utf-8').encode()).hexdigest()
    cache=json.loads(CACHE.read_text(encoding='utf-8')) if CACHE.exists() else {'rows':{}}
    if cache.get('classification_code_sha256') not in (None,code_hash):
        if not refresh: raise SystemExit('Classifier changed; regenerate predictions explicitly before comparing.')
        cache={'rows':{}}
    if not refresh and not CACHE.exists():
        raise SystemExit('Create the classification cache with --refresh-classifications and your confirmed-free key.')
    provider=FreeLLM() if refresh else None
    if refresh and not provider.configured: raise SystemExit('A configured confirmed-free provider is required for classification.')
    if refresh and (cache.get('category_schema_sha256') not in (None,digest(categories)) or
                    cache.get('model') not in (None,provider.model) or
                    cache.get('provider') not in (None,provider.provider)):
        cache={'rows':{}}
    classifier=Resolver(lambda q,e:[],provider,categories=lambda:categories) if refresh else None
    calls=0
    for name,cases in sets.items():
        for case in cases:
            key=name+':'+case['id']
            query=case['query']
            existing=cache['rows'].get(key)
            if existing and existing['query_sha256']==digest(query): continue
            if not refresh: raise SystemExit('Missing/stale prediction for '+key)
            calls+=1
            try:
                prediction=classifier.classify(query)
                error=None
            except (ProviderUnavailable,ValueError) as failure:
                prediction=local_classification(query)
                error=type(failure).__name__
            # No references, expected product, accepted category or corpus text go to the classifier.
            cache['rows'][key]={'query_sha256':digest(query),'classification':prediction.model_dump(),'error':error}
            cache.update(classification_code_sha256=code_hash,category_schema_sha256=digest(categories),
                         provider=provider.provider,model=provider.model,
                         label_origin='Provider predictions from query and allowed taxonomy only; no benchmark labels.',
                         min_call_interval_seconds=provider.interval)
            CACHE.write_text(json.dumps(cache,indent=2),encoding='utf-8')
            print(json.dumps({'classified':key,'product':prediction.product,'category':prediction.category,'error':error}),flush=True)
    if cache.get('category_schema_sha256')!=digest(categories):
        raise SystemExit('Taxonomy changed; review/regenerate the cache before evaluating.')
    return cache,calls


def run(refresh=False):
    sets=query_sets()
    cache,calls=classify_queries(sets,refresh)
    records=load_records(DATA)
    report={'version':'query-enrichment-pilot-v1','measured_at':datetime.now(timezone.utc).isoformat(),
            'corpus_sha256':hashlib.sha256(json.dumps(records,sort_keys=True).encode()).hexdigest(),
            'query_sets_sha256':digest(sets),'classification_cache_sha256':digest(cache),
            'query_builder_sha256':hashlib.sha256((ROOT/'retrieval_query.py').read_text(encoding='utf-8').encode()).hexdigest(),
            'active_sources':sum(r['status']=='active' for r in records),
            'classifier':{k:cache[k] for k in ('provider','model','classification_code_sha256','category_schema_sha256','min_call_interval_seconds')},
            'new_classification_calls_this_run':calls,'query_rewrite_llm_calls':0,
            'settings':{'limit':20,'assessed_k':5,'min_semantic_score':.30,'product_filter':None,'record_type_filter':None},
            'notice':'Same frozen queries, references, corpus, models, ranking and thresholds. Shared cached prediction per query; expected labels never enrich the query. Partial-reference development results, not independent human accuracy.',
            'cohorts':{}}
    with TestClient(create_app(cache_path=ROOT/'runtime/embeddings.json',provider=NoProvider(),access=AccessPolicy())) as client:
        for name,cases in sets.items():
            rows=[]
            for case in cases:
                cached=cache['rows'][name+':'+case['id']]
                prediction=Classification.model_validate(cached['classification']).model_dump()
                row={'id':case['id'],'classification_error':cached['error'],
                     'raw_query':build_search_query(case['query'],prediction,'raw'),
                     'enriched_query':build_search_query(case['query'],prediction,'enriched'),'variants':{}}
                for variant in ('raw','enriched'):
                    row['variants'][variant]={}
                    for mode in ('keyword','semantic','hybrid'):
                        payload={'query':case['query'],'query_mode':variant,'classification':prediction,
                                 'mode':mode,'limit':20,'min_semantic_score':.30}
                        response=client.post('/search',json=payload)
                        response.raise_for_status()
                        ids=[h['id'] for h in response.json()['results']]
                        row['variants'][variant][mode]={'top_5':ids[:5],**reference_metrics(ids,case['references'])}
                rows.append(row)
            aggregates={variant:{mode:{metric:round(sum(r['variants'][variant][mode][metric] for r in rows)/len(rows),4)
                                      for metric in ('reference_hit_at_5','partial_reference_recall_at_5','reference_reciprocal_rank_at_5')}
                                 for mode in ('keyword','semantic','hybrid')} for variant in ('raw','enriched')}
            report['cohorts'][name]={'cases':len(rows),'classification_failures':sum(bool(r['classification_error']) for r in rows),
                                     'metrics':aggregates,'rows':rows}
            print(json.dumps({'cohort':name,'metrics':aggregates}),flush=True)
    RESULT.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'classification_calls':calls,'query_rewrite_llm_calls':0,'results':str(RESULT)},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--refresh-classifications',action='store_true',help='Create/resume predictions with one existing classification call per query. Default uses the committed cache without a key.')
    run(parser.parse_args().refresh_classifications)
