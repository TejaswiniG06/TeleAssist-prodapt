"""Live free-provider diagnostic pilot using the same classification code as resolve."""
import hashlib
import json
from pathlib import Path
from pydantic import ValidationError
from teleassist.retrieval.evidence import load_records
from teleassist.resolution.llm import FreeLLM, ProviderUnavailable
from teleassist.resolution.pipeline import Resolver
from teleassist.retrieval.keyword import DATA


def run():
    path=Path('data/classification_pilot_v1.json')
    pilot=json.loads(path.read_text(encoding='utf-8'))
    categories=sorted({r.get('category','unknown') for r in load_records(DATA)}|{'unknown'})
    provider=FreeLLM()
    if not provider.configured:
        raise SystemExit('This live check requires a locally configured confirmed-free provider; unit tests do not.')
    resolver=Resolver(lambda query,excluded:[],provider,categories=lambda:categories)
    rows=[]
    for case in pilot['cases']:
        row={'id':case['id'],'expected':case['expected']}
        try:
            prediction=resolver.classify(case['complaint']).model_dump()
            row['prediction']=prediction
            row['label_checks']={label:prediction[label] in accepted for label,accepted in case['expected'].items()}
            if case.get('attempted_action'):
                row['attempted_action_present']=any(a['action_id']==case['attempted_action'] for a in prediction['attempted_actions'])
        except (ProviderUnavailable,ValueError,ValidationError) as error:
            row['error']=type(error).__name__
            row['label_checks']={label:False for label in case['expected']}
        rows.append(row)
        print(json.dumps({'case':row['id'],'label_checks':row['label_checks'],'error':row.get('error')}),flush=True)
    scores={label:{'correct':sum(row['label_checks'][label] for row in rows),'total':len(rows)}
            for label in ('product','category','severity','sentiment')}
    report={'version':pilot['version'],'label_origin':pilot['label_origin'],'notice':pilot['notice'],
            'case_sha256':hashlib.sha256(json.dumps(pilot,sort_keys=True).encode()).hexdigest(),
            'provider':provider.provider,'model':provider.model,'scores':scores,'rows':rows}
    Path('runtime').mkdir(exist_ok=True)
    Path('runtime/classification-pilot-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'scores':scores,'notice':pilot['notice']},indent=2))


if __name__=='__main__':
    run()
