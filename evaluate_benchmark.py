"""Frozen partial-reference retrieval pilot and trust-context ablation."""
import hashlib
import json
from pathlib import Path
from fastapi.testclient import TestClient
from access import AccessPolicy
from api import create_app
from evidence import load_records
from resolution import select_evidence, tier
from retrieval import DATA


class NoProvider:
    configured=False


def reference_metrics(ranked, references, k=5):
    references=set(references)
    top=ranked[:k]
    ranks=[rank for rank,item in enumerate(top,1) if item in references]
    return {'reference_hit_at_5':float(bool(ranks)),
            'partial_reference_recall_at_5':len(set(top)&references)/len(references),
            'reference_reciprocal_rank_at_5':1/min(ranks) if ranks else 0.0}


def run():
    path=Path('data/benchmark_v1.json')
    benchmark=json.loads(path.read_text(encoding='utf-8'))
    records=load_records(DATA)
    active={r['id']:r for r in records if r['status']=='active'}
    assert all(reference in active for case in benchmark['cases'] for reference in case['references'])
    corpus_hash=hashlib.sha256(json.dumps(records,sort_keys=True).encode()).hexdigest()
    rows=[]
    with TestClient(create_app(cache_path=Path('runtime/embeddings.json'),provider=NoProvider(),access=AccessPolicy())) as client:
        for case in benchmark['cases']:
            row={'id':case['id'],'references':case['references'],'modes':{}}
            for mode in ('keyword','semantic','hybrid'):
                response=client.post('/search',json={'query':case['query'],'mode':mode,'limit':20})
                response.raise_for_status()
                hits=response.json()['results']
                ids=[hit['id'] for hit in hits]
                row['modes'][mode]={'top_5':ids[:5],**reference_metrics(ids,case['references'])}
                if mode=='hybrid':
                    raw=hits[:8]
                    trusted=select_evidence(hits,case['product'],limit=8)
                    row['context_ablation']={
                        'raw_hybrid':{'ids':[h['id'] for h in raw],'tiers':[tier(h['record']) for h in raw]},
                        'trust_and_product':{'ids':[h['id'] for h in trusted],'tiers':[tier(h['record']) for h in trusted]}}
            rows.append(row)
    aggregates={}
    for mode in ('keyword','semantic','hybrid'):
        aggregates[mode]={key:round(sum(row['modes'][mode][key] for row in rows)/len(rows),4)
                          for key in ('reference_hit_at_5','partial_reference_recall_at_5','reference_reciprocal_rank_at_5')}
    strata={product:{mode:round(sum(r['modes'][mode]['reference_hit_at_5'] for r,c in zip(rows,benchmark['cases']) if c['product']==product)/
                                sum(c['product']==product for c in benchmark['cases']),4)
                     for mode in aggregates}
            for product in sorted({c['product'] for c in benchmark['cases']})}
    context={name:{'mean_unverified_per_8':round(sum(row['context_ablation'][name]['tiers'].count('unverified') for row in rows)/len(rows),3),
                   'cases_with_reference':sum(bool(set(row['context_ablation'][name]['ids'])&set(row['references'])) for row in rows)}
             for name in ('raw_hybrid','trust_and_product')}
    report={'benchmark_version':benchmark['version'],'benchmark_sha256':hashlib.sha256(json.dumps(benchmark,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
            'corpus_sha256':corpus_hash,'active_sources':len(active),'cases':len(rows),
            'label_origin':benchmark['label_origin'],'split':benchmark['split'],'notice':benchmark['notice'],
            'metrics':aggregates,'product_reference_hit_at_5':strata,'context_ablation':context,'rows':rows}
    Path('runtime').mkdir(exist_ok=True)
    Path('runtime/benchmark-v1-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='rows'},indent=2))


if __name__=='__main__':
    run()
