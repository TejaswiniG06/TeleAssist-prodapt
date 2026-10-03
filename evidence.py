"""Load public references and reserve query-only records to avoid self-retrieval."""
import hashlib
import json
from pathlib import Path
from privacy import mask

ROOT = Path(__file__).parent


def public_records(path=None):
    path = Path(path or ROOT / 'scratch/prepared/tobi_candidates.json')
    if not path.exists():
        return []
    records = []
    for candidate in json.loads(path.read_text(encoding='utf-8')):
        complaint = mask(candidate['body'].replace('\\n', '\n'))[0]
        answer = mask(candidate['answer'].replace('\\n', '\n'))[0]
        records.append(dict(id=f"PUBLIC-{candidate['source_row']:05d}", version=1, status='active',
                            record_type='unverified_ticket', title=mask(candidate['subject'])[0],
                            complaint=complaint, suggested_steps=answer, outcome='unknown',
                            resolution_verified=False, evidence_tier='unverified',
                            product='unknown', category='unknown', provenance='public_origin_unverified',
                            source_url=candidate['source_url'], source_row=candidate['source_row'],
                            source_labels=candidate['source_labels'], creator=candidate['creator'],
                            license=candidate['license'],
                            applicability='Adjacent IT/device ticket; applicability and success are unverified.'))
    return records


def build_public_evaluation(records, path=None):
    path = Path(path or ROOT / 'data/public_evaluation.json')
    # Stable query selection without using retrieval scores or generation success.
    chosen = sorted(records, key=lambda r: hashlib.sha256(r['id'].encode()).hexdigest())[:25]
    cases = [dict(id='EVAL-' + r['id'], query=r['complaint'], excluded_source_id=r['id'],
                  source_url=r['source_url'], source_row=r['source_row'],
                  creator=r['creator'], license=r['license'],
                  split='held_out_query', annotation_status='pending_manual_relevance_review',
                  origin='public_origin_unverified',
                  expected_behavior='Clarify applicability; do not claim a successful fix from an unverified reply.')
             for r in chosen]
    path.write_text(json.dumps(cases, indent=2), encoding='utf-8')
    return cases


def load_records(data_path, include_public=True):
    records = json.loads(Path(data_path).read_text(encoding='utf-8'))
    for r in records:
        if r['record_type'] == 'article':
            r.setdefault('evidence_tier', 'kb')
        elif r['record_type'] == 'resolved_ticket':
            r.setdefault('outcome_status', 'resolved')
            r.setdefault('evidence_tier', 'resolved')
    synthetic = ROOT / 'data/synthetic_tickets.json'
    if include_public:
        if synthetic.exists():
            records.extend(json.loads(synthetic.read_text(encoding='utf-8')))
        records.extend(public_records())
    ids = [r['id'] for r in records]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate source IDs.')
    return records


if __name__ == '__main__':
    records = public_records()
    cases = build_public_evaluation(records)
    print(json.dumps({'indexed_public_tickets': len(records), 'evaluation_queries': len(cases)}))
