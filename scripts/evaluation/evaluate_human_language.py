"""Separate casual retrieval pilot and matched attempted-action ablation."""
from teleassist.common.paths import PROJECT_ROOT
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from fastapi.testclient import TestClient
from teleassist.common.access import AccessPolicy
from teleassist.services.combined import create_app
from scripts.evaluation.evaluate_benchmark import reference_metrics, NoProvider
from teleassist.resolution.llm import FreeLLM, ProviderUnavailable
from teleassist.common.privacy import mask
from teleassist.resolution.pipeline import Resolver, local_classification, source_actions, select_evidence


ROOT = PROJECT_ROOT
SUITE = ROOT / 'data/human_language_v1.json'
REPORT = ROOT / 'runtime/human-language-report.json'
NO_REPEAT = 'Do not repeat explicitly attempted actions, including those with unknown outcomes. '

# Evaluation labels/wording checks are separate from the implementation's alias function.
ACTION_WORDING = {
    'restart_router':r'(?:restart|reboot|power.?cycl)\w*.*(?:router|gateway|box)|(?:router|gateway|box).*?(?:restart|reboot|power.?cycl)',
    'toggle_airplane_mode':r'(?:airplane|flight)\s+mode',
    'compare_wired_connection':r'(?:compar\w*|test\w*).*(?:wired|ethernet)|(?:wired|ethernet).*?(?:compar\w*|test\w*)',
    'collect_speed_measurement':r'(?:measur\w*|test\w*).*(?:speed)|speed.*?(?:measur\w*|test\w*)',
    'move_router':r'(?:mov\w*|relocat\w*|reposition\w*).*?(?:router|gateway)|(?:router|gateway).*?(?:mov\w*|relocat\w*|reposition\w*)',
    'pause_background_download':r'(?:paus\w*|stop\w*).*?download',
    'check_device_scope':r'(?:ask|check|confirm|identify|determine).*?(?:one device|all devices|several devices|other devices|device scope)'
}


def action_matches(step, labels):
    wording = step.get('instruction', '')
    return [label for label in labels if step.get('action_id') == label or
            re.search(ACTION_WORDING[label], wording, re.I)]


def repetition(result, labels):
    matches = [label for step in result.get('steps', []) for label in action_matches(step, labels)]
    return {'repeated':bool(matches), 'repeated_actions':sorted(set(matches)),
            'step_count':len(result.get('steps', []))}


def repetition_summary(rows, name):
    outcomes = [row[name] for row in rows]
    repeats = sum(row['repeated'] for row in outcomes)
    answers = sum(row['step_count'] > 0 for row in outcomes)
    return {'repeated_cases':repeats, 'cases':len(rows),
            'repeated_fix_rate':repeats/len(rows) if rows else None,
            'answers_with_steps':answers,
            'repetition_among_answers_with_steps':repeats/answers if answers else None,
            'provider_fallbacks':sum(row['reason']=='provider_unavailable' for row in outcomes),
            'grounding_fallbacks':sum(row['reason']=='grounding_validation_failed' for row in outcomes)}


def feature_summary(rows, planned_cases):
    for row in rows:
        # Expected no-evidence abstention is not a provider/validation failure.
        row['checks']['provider_completed'] = not row.get('classification_error',False) and row.get('ours',{}).get('reason') not in ('provider_unavailable','grounding_validation_failed')
    return {**{label:{'correct':sum(row['checks'].get(label,False) for row in rows),'total':planned_cases}
               for label in ('product','category','churn')},
            'all_requested_checks':{'passed_cases':sum(all(row['checks'].values()) for row in rows),'cases':planned_cases}}


def citation_check(result, client):
    steps = result.get('steps', [])
    if not steps: return {'applicable':False, 'passed':None, 'checked_steps':0}
    valid = result.get('citation_check') == 'passed'
    for step in steps:
        response = client.get('/sources/'+step['source_id'],params={'version':step['source_version']})
        if response.status_code != 200:
            valid = False
            continue
        record = response.json()
        action = next((a for a in source_actions(record) if a['action_id']==step['action_id']),None)
        valid = valid and record['version']==step['source_version'] and action is not None
        valid = valid and bool(action and step['support_quote'] in action['instruction'])
        valid = valid and any(c['id']==step['source_id'] and c['version']==step['source_version'] for c in result['citations'])
    return {'applicable':True, 'passed':bool(valid), 'checked_steps':len(steps)}


class BaselineProvider:
    """Same provider/checker; remove only attempted-action prompting."""
    configured = True
    def __init__(self, provider): self.provider = provider
    def generate(self, system, payload, max_tokens=4000):
        if 'options' in payload:
            if NO_REPEAT not in system: raise ValueError('Baseline prompt adapter needs review.')
            system = system.replace(NO_REPEAT, '')
        return self.provider.generate(system, payload, max_tokens)


class FixedClassificationResolver(Resolver):
    def __init__(self, *args, classification, protect_attempts=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.prediction, self.protect_attempts = classification, protect_attempts
    def classify(self, context):
        prediction = self.prediction.model_copy(deep=True)
        if not self.protect_attempts: prediction.attempted_actions = []
        return prediction


class TracedProvider(FreeLLM):
    def __init__(self):
        super().__init__()
        self.forbidden, self.masking_ok = [], True
    def generate(self, system, payload, max_tokens=4000):
        serialized = json.dumps(payload)
        self.masking_ok = self.masking_ok and not any(value in serialized for value in self.forbidden)
        return super().generate(system, payload, max_tokens)


def hard_retrieval(client, cases):
    rows=[]
    for case in cases:
        row={'id':case['id'], 'modes':{}}
        for mode in ('keyword','semantic','hybrid'):
            response=client.post('/search',json={'query':case['query'],'mode':mode,'limit':20})
            response.raise_for_status()
            ids=[h['id'] for h in response.json()['results']]
            row['modes'][mode]={'top_5':ids[:5], **reference_metrics(ids,case['references'])}
        rows.append(row)
        print(json.dumps({'hard_query':case['id'],'hit_at_5':{m:v['reference_hit_at_5'] for m,v in row['modes'].items()}}),flush=True)
    summary={mode:{metric:round(sum(row['modes'][mode][metric] for row in rows)/len(rows),4)
                   for metric in ('reference_hit_at_5','partial_reference_recall_at_5','reference_reciprocal_rank_at_5')}
             for mode in ('keyword','semantic','hybrid')}
    return {'cases':len(rows),'metrics':summary,'rows':rows}


def resolve_hits(client, context):
    hits=[]
    for kind in ('article','resolved_ticket','unverified_ticket','unresolved_ticket'):
        response=client.post('/search',json={'query':context[:2000],'mode':'hybrid','limit':20,
                                            'record_type':kind,'min_semantic_score':.32})
        response.raise_for_status()
        hits.extend(h for h in response.json()['results'] if h.get('components',{}).get('semantic',{}).get('score',0)>=.32)
    return hits


def live_cases(client, suite, report, provider):
    categories=client.get('/taxonomy').json()['categories']
    classifier=Resolver(lambda q,e:[],provider,categories=lambda:categories)
    feature_ids={c['id'] for c in suite['feature_cases']}
    cases=suite['feature_cases'] + suite['extra_attempt_cases']
    rows, paired = [], []
    for index,case in enumerate(cases):
        complaint=mask(case['complaint'])[0]
        observations=mask(case.get('observations',''))[0]
        context=complaint+('\n'+observations if observations else '')
        provider.forbidden=case.get('mask_values',[])
        provider.masking_ok=True
        classification_failed=False
        try:
            classification=classifier.classify(context)
        except (ProviderUnavailable,ValueError):
            classification=local_classification(context)
            classification_failed=True
        hits=resolve_hits(client,context)
        common=dict(search=lambda q,e:hits,classification=classification,categories=lambda:categories)
        ours=FixedClassificationResolver(provider=provider,**common)
        baseline=FixedClassificationResolver(provider=BaselineProvider(provider),protect_attempts=False,**common)
        labels=case.get('attempted',[])
        outcomes={}
        # Alternate order; one shared classification/retrieval context per paired case.
        order=[('ours',ours),('plain_rag',baseline)] if index%2 else [('plain_rag',baseline),('ours',ours)]
        if not labels: order=[('ours',ours)]
        for name,resolver in order:
            result=resolver.resolve(case['complaint'],case.get('observations',''),query_mode='raw')
            outcomes[name]={'status':result['status'],'reason':result['reason'],
                            'generation':result['generation'], **repetition(result,labels),
                            'citation':citation_check(result,client),'result':result}
        prediction=classification.model_dump()
        checks={'product':prediction['product'] in case['product'],
                'category':prediction['category'] in case['category'],
                'provider_completed':not classification_failed and outcomes['ours']['generation']=='llm'}
        if labels:
            extracted={a['action_id'] for a in prediction['attempted_actions']}
            checks.update(attempt_extraction=all(label in extracted for label in labels),
                          no_repeated_fix=not outcomes['ours']['repeated'])
            selected=select_evidence(hits,classification.product)
            available=sorted({a for h in selected for step in source_actions(h['record']) for a in action_matches(step,labels)})
            paired.append({'id':case['id'],'expected_actions':labels,'available_repeated_actions':available,
                           'extracted_actions':sorted(extracted),**outcomes})
        if 'churn' in case: checks['churn']=prediction['churn_risk']==case['churn']
        if case.get('must_abstain'):
            checks['abstention']=outcomes['ours']['status'] in ('clarification','escalation') and not outcomes['ours']['step_count']
        if provider.forbidden:
            serialized=json.dumps(outcomes['ours']['result'])
            checks['masking']=provider.masking_ok and not any(value in serialized for value in provider.forbidden)
        if case.get('injection'):
            emitted=outcomes['ours']['result']['answer'].lower()
            checks['no_injection_promise']='refund' not in emitted and 'factory reset' not in emitted
        if case['id']=='U05':
            ids=[s['source_id'] for s in outcomes['ours']['result']['steps']]
            records=[client.get('/sources/'+s).json() for s in ids]
            checks['no_broadband_steps']=all(r.get('product') in ('mobile','unknown') for r in records)
        row={'id':case['id'],'feature_case':case['id'] in feature_ids,'classification_error':classification_failed,'prediction':prediction,
             'checks':checks,'ours':outcomes['ours']}
        rows.append(row)
        report['live_rows'],report['paired_rows']=rows,paired
        save(report)
        print(json.dumps({'case':case['id'],'checks':checks,'paired_repetition':{name:value['repeated'] for name,value in outcomes.items()}}),flush=True)
    features=[r for r in rows if r['id'] in feature_ids]
    report['feature_metrics']=feature_summary(features,len(suite['feature_cases']))
    cited=[r['ours']['citation'] for r in rows if 'ours' in r and r['ours']['citation']['applicable']]
    report['citation_metrics']={'passed_step_bearing_answers':sum(c['passed'] for c in cited),
                              'step_bearing_answers':len(cited),'checked_steps':sum(c['checked_steps'] for c in cited),
                              'notice':'No-step outcomes excluded; mechanical source/version/quote checks, not full entailment.'}
    report['repeated_fix_metrics']={name:repetition_summary(paired,name) for name in ('plain_rag','ours')}
    report['attempt_extraction']={'correct_cases':sum(set(r['expected_actions'])<=set(r['extracted_actions']) for r in paired),'cases':len(paired)}
    report['cases_with_repeat_available']=sum(bool(r['available_repeated_actions']) for r in paired)


def save(report):
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text(json.dumps(report,indent=2),encoding='utf-8')


def export_summary():
    """Publish compact measurements without raw complaint/provider traces."""
    report=json.loads(REPORT.read_text(encoding='utf-8'))
    if not report['complete'] or 'feature_metrics' not in report:
        raise SystemExit('Complete the live evaluation before exporting its summary.')
    suite=json.loads(SUITE.read_text(encoding='utf-8'))
    digest=hashlib.sha256(json.dumps(suite,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if report['suite_sha256']!=digest:
        raise SystemExit('Case set changed; do not relabel the recorded run.')
    if report['resolution_code_sha256']!=hashlib.sha256((ROOT/'teleassist/resolution/pipeline.py').read_bytes()).hexdigest():
        raise SystemExit('Resolution code changed; rerun before publishing a current-code checkpoint.')
    from teleassist.retrieval.evidence import load_records
    from teleassist.retrieval.keyword import DATA
    report['corpus_sha256']=hashlib.sha256(json.dumps(load_records(DATA),sort_keys=True).encode()).hexdigest()
    features=[r for r in report['live_rows'] if r['feature_case']]
    report['feature_metrics']=feature_summary(features,len(suite['feature_cases']))
    save(report)
    summary={k:v for k,v in report.items() if k not in ('live_rows','paired_rows')}
    summary['feature_rows']=[{'id':r['id'],'prediction':{k:r['prediction'][k] for k in ('product','category','churn_risk')},
                             'checks':r['checks'],'status':r['ours']['status'],'reason':r['ours']['reason']} for r in report['live_rows']]
    for row in report['paired_rows']:
        ours=row['ours']['result']['retrieved_sources']
        baseline=row['plain_rag']['result']['retrieved_sources']
        if ours!=baseline: raise SystemExit('Paired source contexts differ; review the baseline.')
        row['context_source_ids']=[s['id'] for s in ours]
    summary['paired_rows']=[{**{k:r[k] for k in ('id','expected_actions','available_repeated_actions','extracted_actions','context_source_ids')},
                            **{name:{k:v for k,v in r[name].items() if k!='result'} for name in ('plain_rag','ours')}}
                           for r in report['paired_rows']]
    path=ROOT/'data/human_language_results_v1.json'
    path.write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('paired_rows','feature_rows','hard_retrieval')},indent=2))


def run(live=False):
    suite=json.loads(SUITE.read_text(encoding='utf-8'))
    report={'version':suite['version'],'started_at':datetime.now(timezone.utc).isoformat(),
            'suite_sha256':hashlib.sha256(json.dumps(suite,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
            'resolution_code_sha256':hashlib.sha256((ROOT/'teleassist/resolution/pipeline.py').read_bytes()).hexdigest(),
            'label_origin':suite['label_origin'],'notice':suite['notice'],
            'baseline':'Matched plain RAG ablation: same model, hybrid context, trust selection and citation checker; no attempted-action extraction in draft or exclusion/prompt guard.',
            'complete':False}
    with TestClient(create_app(cache_path=ROOT/'runtime/embeddings.json',provider=NoProvider(),access=AccessPolicy())) as client:
        report['active_sources']=client.get('/health').json()['active_sources']
        report['hard_retrieval']=hard_retrieval(client,suite['hard_queries'])
        save(report)
        if live:
            provider=TracedProvider()
            if not provider.configured: raise SystemExit('Live comparison requires a locally configured confirmed-free provider.')
            report.update(provider=provider.provider,model=provider.model,min_call_interval_seconds=provider.interval)
            live_cases(client,suite,report,provider)
    report['complete']=True
    report['completed_at']=datetime.now(timezone.utc).isoformat()
    save(report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('live_rows','paired_rows','hard_retrieval')},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--live',action='store_true',help='Use the configured free provider for user cases and the paired comparison.')
    parser.add_argument('--export-summary',action='store_true',help='Export a completed live run without making provider calls.')
    args=parser.parse_args()
    if args.export_summary: export_summary()
    else: run(args.live)
