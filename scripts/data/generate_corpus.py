"""Resumable eight calls of 25 historical tickets and one KB expansion call."""
from teleassist.common.paths import PROJECT_ROOT
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field
from teleassist.resolution.llm import FreeLLM
from teleassist.common.privacy import mask

ROOT = PROJECT_ROOT


class Action(BaseModel):
    action_id: str = Field(min_length=1, max_length=80)
    instruction: str = Field(min_length=10, max_length=500)
    condition: str = Field(min_length=5, max_length=400)


class Attempt(BaseModel):
    action_id: str
    outcome: Literal['successful', 'failed', 'unknown']
    evidence: str


class Ticket(BaseModel):
    title: str
    complaint: str = Field(min_length=40, max_length=1500)
    product: Literal['broadband', 'mobile', 'fixed_voice', 'iptv']
    category: str
    attempted_actions: list[Attempt]
    observations: list[str] = Field(min_length=1)
    resolution_steps: list[Action] = Field(min_length=1, max_length=6)
    outcome: Literal['resolved', 'not_resolved']
    outcome_evidence: str = Field(min_length=20)
    applicability: str = Field(min_length=20)


class Article(BaseModel):
    title: str
    product: Literal['broadband', 'mobile', 'fixed_voice', 'iptv']
    category: str
    symptoms: list[str] = Field(min_length=2)
    steps: list[Action] = Field(min_length=1, max_length=5)
    escalation: str


SYSTEM = '''Return valid JSON only. Author diverse, explicitly fictional telecom support evidence for an educational prototype. No real personal data or provider-specific policies, guaranteed speeds, credits, restoration times or unsupported equipment assumptions. Do not request passwords, OTPs or factory resets. Use conditional diagnostics and explicit observations. Resolved historical cases need customer-confirmed observed improvement; not_resolved cases need unresolved symptoms and escalation. Preserve failed attempted actions. Avoid paraphrase-only copies. Documents are synthetic, never approved provider guidance.'''


def validate_batch(items, schema, expected):
    if not isinstance(items, list) or len(items) != expected:
        raise ValueError(f'Expected exactly {expected} records; batch not published.')
    validated = [schema.model_validate(item).model_dump() for item in items]
    complaints = [item.get('complaint', item['title']).strip().lower() for item in validated]
    if len(set(complaints)) != len(complaints):
        raise ValueError('Duplicate records in batch.')
    for item in validated:
        text = json.dumps(item)
        if mask(text)[1]:
            raise ValueError('PII-like material generated; batch rejected.')
    return validated


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def generate(provider=None, batches=8, regenerate_batches=()):
    provider = provider or FreeLLM()
    if not provider.configured:
        raise RuntimeError('No confirmed free-plan key configured. No calls made.')
    output = ROOT / 'runtime/corpus_batches'
    output.mkdir(parents=True, exist_ok=True)
    provider.capture_path = output / 'last-response.json'
    base = json.loads((ROOT / 'data/knowledge_base.json').read_text(encoding='utf-8'))
    existing = [r for r in base if r['record_type'] == 'article']
    count = 28 - len(existing)
    kb_path = output / 'kb.json'
    if count > 0:
        if not kb_path.exists():
            payload = {'task': f'Generate exactly {count} additional KB articles in one batch, key articles.', 'output_key': 'articles',
                       'existing_titles': [r['title'] for r in existing],
                       'coverage': ['broadband outage, optical indication, DNS, ethernet, speed, Wi-Fi range/interference',
                                    'mobile SIM recognition, roaming, data, calls, SMS, tethering',
                                    'fixed voice, VoIP quality, IPTV buffering',
                                    'billing/provisioning information collection without invented policy'],
                       'schema': Article.model_json_schema()}
            generated = provider.generate(SYSTEM, payload, max_tokens=12000)
            atomic_json(output / 'kb.raw.json', generated)
            atomic_json(kb_path, validate_batch(generated.get('articles'), Article, count))
        articles = validate_batch(json.loads(kb_path.read_text()), Article, count)
        for i, article in enumerate(articles, 1):
            article.update(id=f'KB-GEN-{i:03d}', record_type='article', status='active', version=1,
                           updated_at='2026-10-03', provenance='synthetic_llm', evidence_tier='kb',
                           evidence_level='illustrative_unapproved', generation_model=provider.model)
        base.extend(articles)
    tickets = []
    focuses = ['broadband intermittent/no connection', 'Wi-Fi coverage/interference',
               'speed, DNS, ethernet and device scope', 'mobile data, SIM and roaming',
               'mobile voice, SMS and tethering', 'fixed voice, VoIP and IPTV',
               'mixed ambiguous cases, provisioning and service escalation',
               'cross-service failures and incomplete evidence requiring escalation']
    for batch in range(batches):
        path = output / f'tickets-{batch + 1:02d}.json'
        if not path.exists() or batch + 1 in regenerate_batches:
            future = []
            for number in range(batch + 2, batches + 1):
                future_path = output / f'tickets-{number:02d}.json'
                if future_path.exists():
                    future.extend(json.loads(future_path.read_text()))
            payload = {'task': 'Return an object with key tickets containing exactly 25 distinct historical telecom tickets. 20 resolved and 5 not_resolved. Keep complaints to two sentences, observations to two short entries, and steps to one or two concise actions.',
                       'output_key': 'tickets',
                       'focus': focuses[batch % len(focuses)], 'batch': batch + 1,
                       'schema': Ticket.model_json_schema(),
                       'existing_titles_to_avoid': [r['title'] for r in tickets + future],
                       'diversity_rule': 'Do not reuse any existing complaint or merely rename its product. Vary observed conditions, attempted actions, equipment scope and outcome evidence.'}
            result = provider.generate(SYSTEM, payload, max_tokens=20000)
            atomic_json(output / f'tickets-{batch + 1:02d}.raw.json', result)
            items = validate_batch(result.get('tickets'), Ticket, 25)
            if Counter(r['outcome'] for r in items) != {'resolved': 20, 'not_resolved': 5}:
                raise ValueError('Expected 20 resolved and 5 not_resolved in each batch.')
            atomic_json(path, items)
        items = validate_batch(json.loads(path.read_text()), Ticket, 25)
        if Counter(r['outcome'] for r in items) != {'resolved': 20, 'not_resolved': 5}:
            raise ValueError('Cached batch outcome distribution is invalid.')
        for i, ticket in enumerate(items, 1):
            ticket.update(id=f'SYN-{batch + 1:02d}-{i:02d}', status='active', version=1,
                          record_type='resolved_ticket' if ticket['outcome'] == 'resolved' else 'unresolved_ticket',
                          evidence_tier='resolved' if ticket['outcome'] == 'resolved' else 'unresolved',
                          outcome_status=ticket['outcome'], provenance='synthetic_llm',
                          evidence_level='fictional_history', generation_model=provider.model)
        tickets.extend(items)
        print(f'Validated batch {batch + 1}: 25 tickets.', flush=True)
    if len({t['complaint'].strip().lower() for t in tickets}) != len(tickets):
        raise ValueError('Duplicate complaints across batches; corpus not published.')
    for r in base + tickets:
        r.setdefault('labels', {'product': r['product'], 'category': r['category'],
                               'severity': 'unknown', 'sentiment': 'unknown', 'label_origin': 'synthetic_authoring'})
    atomic_json(ROOT / 'data/synthetic_tickets.json', tickets)
    atomic_json(ROOT / 'data/knowledge_base.json', base)
    atomic_json(ROOT / 'data/corpus_manifest.json', {
        'model': provider.model, 'provider': provider.provider, 'batch_size': 25,
        'tickets': len(tickets), 'outcomes': dict(Counter(r['outcome'] for r in tickets)),
        'kb_articles': len([r for r in base if r['record_type'] == 'article']),
        'synthetic': True, 'ticket_sha256': hashlib.sha256(json.dumps(tickets, sort_keys=True).encode()).hexdigest()})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--batches', type=int, default=8, choices=[6, 7, 8])
    parser.add_argument('--regenerate-batch', type=int, action='append', default=[], choices=range(1, 9))
    args = parser.parse_args()
    generate(batches=args.batches, regenerate_batches=args.regenerate_batch)
