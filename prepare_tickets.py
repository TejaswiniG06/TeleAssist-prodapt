"""Auditable candidate filter. External answers are never imported as confirmed fixes."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import re

PATTERN = re.compile(r'\b(broadband|wi[ -]?fi|router|modem|fiber|fibre|telecom|5g|4g|sim card|mobile network|internet connection|internet service|voip)\b', re.I)


def prepare(source, destination):
    source, destination = Path(source), Path(destination)
    rows = list(csv.DictReader(source.open(encoding='utf-8-sig', newline='')))
    candidates = []
    seen = set()
    for row_number, row in enumerate(rows, 2):
        text = row['subject'] + '\n' + row['body']
        matches = sorted(set(m.group(0).lower() for m in PATTERN.finditer(text)))
        if row['language'] != 'en' or not matches:
            continue
        digest = hashlib.sha256(text.encode()).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        candidates.append({'source_row': row_number, 'subject': row['subject'],
                           'body': row['body'], 'answer': row['answer'],
                           'source_labels': {k: v for k, v in row.items() if k not in ('subject', 'body', 'answer')},
                           'matched_terms': matches, 'review_status': 'candidate_only',
                           'resolution_verified': False, 'provenance': 'public_origin_unverified',
                           'source_url': 'https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets',
                           'creator': 'Tobi-Bueck / Softoft', 'license': 'CC-BY-NC-4.0'})
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'tobi_candidates.json').write_text(json.dumps(candidates, indent=2), encoding='utf-8')
    audit = {'file': source.name, 'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
             'rows': len(rows), 'columns': list(rows[0]) if rows else [],
             'languages': dict(Counter(r['language'] for r in rows)),
             'english_telecom_candidates_deduplicated': len(candidates),
             'candidate_queues': dict(Counter(r['source_labels']['queue'] for r in candidates)),
             'filter': PATTERN.pattern, 'grounding_imported': 0}
    (destination / 'tobi_audit.json').write_text(json.dumps(audit, indent=2), encoding='utf-8')
    print(json.dumps(audit, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('csv_path')
    parser.add_argument('--output', default='scratch/prepared')
    args = parser.parse_args()
    prepare(args.csv_path, args.output)
