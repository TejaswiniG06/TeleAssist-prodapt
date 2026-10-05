"""Reuse validated replacement records from an overlong LLM batch; never invent outcomes."""
from teleassist.common.paths import PROJECT_ROOT
import argparse
from collections import Counter
import json
from pathlib import Path
from scripts.data.generate_corpus import Ticket, atomic_json, validate_batch


def repair(number):
    folder = PROJECT_ROOT / 'runtime/corpus_batches'
    path = folder / f'tickets-{number:02d}.json'
    rows = validate_batch(json.loads(path.read_text()), Ticket, 25)
    raw = json.loads((folder / f'tickets-{number:02d}.raw.json').read_text())['tickets']
    other = [r for p in folder.glob('tickets-??.json') if p != path for r in json.loads(p.read_text())]
    occupied = {r['complaint'].strip().lower() for r in other}
    repaired = []
    replaced = []
    for position, row in enumerate(rows, 1):
        if row['complaint'].strip().lower() in occupied:
            replacement = None
            for candidate in raw:
                if candidate.get('outcome') != row['outcome'] or candidate.get('complaint', '').strip().lower() in occupied:
                    continue
                try:
                    replacement = validate_batch([candidate], Ticket, 1)[0]
                except ValueError:
                    continue
                break
            if replacement is None:
                raise ValueError('Insufficient valid unique replacements; nothing published.')
            row = replacement
            replaced.append(position)
        repaired.append(row)
        occupied.add(row['complaint'].strip().lower())
    assert Counter(r['outcome'] for r in repaired) == {'resolved': 20, 'not_resolved': 5}
    atomic_json(path, validate_batch(repaired, Ticket, 25))
    atomic_json(folder / f'repair-{number:02d}.json', {'batch': number, 'replaced_positions': replaced,
                                                    'raw_records_returned': len(raw), 'published_records': 25})
    print(json.dumps({'repaired_batch': number, 'replaced_duplicates': len(replaced), 'records': 25}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('batch', type=int, choices=range(1, 9))
    repair(parser.parse_args().batch)
