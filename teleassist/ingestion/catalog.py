"""Versioned evidence snapshots: prepare in background, publish in one swap."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from threading import Lock
from typing import Literal
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field, model_validator
from teleassist.common.privacy import mask
from teleassist.resolution.pipeline import SUSPICIOUS
from teleassist.retrieval.keyword import KeywordIndex
from teleassist.retrieval.semantic import SemanticIndex


class Action(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action_id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')
    instruction: str = Field(min_length=10, max_length=1500)
    condition: str = Field(min_length=1, max_length=1500)


class EvidenceRecord(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')
    title: str = Field(min_length=3, max_length=250)
    record_type: Literal['article', 'resolved_ticket', 'unresolved_ticket', 'unverified_ticket']
    product: Literal['broadband', 'mobile', 'fixed_voice', 'iptv', 'unknown']
    category: str = Field(pattern=r'^[a-z][a-z0-9_]{0,79}$')
    status: Literal['active', 'retired'] = 'active'
    provenance: Literal['synthetic_demo', 'synthetic_llm', 'reviewed_internal', 'public_origin_unverified']
    complaint: str = Field(default='', max_length=5000)
    observations: list[str] = Field(default_factory=list, max_length=20)
    symptoms: list[str] = Field(default_factory=list, max_length=20)
    steps: list[Action] = Field(default_factory=list, max_length=20)
    resolution_steps: list[Action] = Field(default_factory=list, max_length=20)
    suggested_steps: str = Field(default='', max_length=5000)
    outcome: Literal['resolved', 'not_resolved', 'unknown'] = 'unknown'
    outcome_evidence: str = Field(default='', max_length=2000)
    applicability: str = Field(min_length=5, max_length=2000)
    escalation: str = Field(default='', max_length=2000)
    source_url: str = Field(default='', max_length=1000)
    creator: str = Field(default='', max_length=250)
    license: str = Field(default='', max_length=100)

    @model_validator(mode='after')
    def coherent(self):
        if any(len(s) > 1500 for s in self.observations + self.symptoms):
            raise ValueError('Observation/symptom too long.')
        if self.record_type == 'article' and (not self.steps or self.outcome != 'unknown' or self.resolution_steps):
            raise ValueError('Articles need guidance, not historical outcome/steps.')
        if self.record_type != 'article' and (not self.complaint.strip() or self.steps):
            raise ValueError('Tickets need a complaint and no article steps.')
        if self.record_type == 'resolved_ticket' and (self.outcome != 'resolved' or not self.outcome_evidence.strip() or not self.resolution_steps):
            raise ValueError('Resolved history needs steps and explicit outcome evidence.')
        if self.record_type == 'unresolved_ticket' and self.outcome != 'not_resolved':
            raise ValueError('Unresolved history must say not_resolved.')
        if self.record_type == 'unverified_ticket' and (self.outcome != 'unknown' or self.resolution_steps or not self.suggested_steps.strip()):
            raise ValueError('Unverified tickets contain suggestions, not verified steps.')
        if self.provenance == 'public_origin_unverified' and self.record_type != 'unverified_ticket':
            raise ValueError('Public unverified evidence cannot be promoted by changing its type.')
        if self.provenance == 'public_origin_unverified' and not all((self.source_url.strip(),self.creator.strip(),self.license.strip())):
            raise ValueError('Public references require source URL, creator and licence.')
        actions = self.steps + self.resolution_steps
        if len({a.action_id for a in actions}) != len(actions):
            raise ValueError('Duplicate action IDs.')
        text = json.dumps(self.model_dump())
        if SUSPICIOUS.search(text):
            raise ValueError('Evidence contains disallowed instruction patterns; review it manually.')
        return self

    def versioned(self, version):
        # Mask recursively before persistence; IDs and action IDs stay stable.
        def scrub(value):
            if isinstance(value, str):
                return mask(value)[0]
            if isinstance(value, list):
                return [scrub(v) for v in value]
            if isinstance(value, dict):
                return {k: v if k in ('id', 'action_id') else scrub(v) for k, v in value.items()}
            return value
        record = scrub(self.model_dump())
        kind = self.record_type
        record.update(version=version, updated_at=datetime.now(timezone.utc).isoformat(),
                      evidence_tier={'article':'kb', 'resolved_ticket':'resolved',
                                     'unresolved_ticket':'unresolved', 'unverified_ticket':'unverified'}[kind])
        if kind.endswith('ticket'):
            record['outcome_status'] = self.outcome
        return record


class Change(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_version: int = Field(ge=0)
    record: EvidenceRecord


class IngestRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_index_version: int = Field(ge=1)
    changes: list[Change] = Field(min_length=1, max_length=50)


class Conflict(ValueError):
    pass


@dataclass
class Snapshot:
    version: int
    records: list
    keyword: KeywordIndex
    semantic: SemanticIndex | None = None
    semantic_error: bool = False


class Catalog:
    def __init__(self, records, encoder=None, cache_path=None, state_path=None):
        self.encoder, self.cache_path = encoder, cache_path
        self.state_path = Path(state_path) if state_path else None
        self.lock, self.embedding_lock = Lock(), Lock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='evidence-ingest')
        self.overrides, self.audit, self.jobs, self.history = {}, [], {}, {}
        version = 1
        if self.state_path and self.state_path.exists():
            stored = json.loads(self.state_path.read_text(encoding='utf-8'))
            self.overrides, self.audit = stored['overrides'], stored['audit']
            self.history = stored.get('history', {})
            version = stored['index_version']
        by_id = {r['id']: r for r in records}
        for record in records:
            self.history.setdefault(f"{record['id']}:{record['version']}", record)
        by_id.update(self.overrides)
        for record in self.overrides.values():
            self.history.setdefault(f"{record['id']}:{record['version']}", record)
        self.all_records = by_id
        active = [r for r in by_id.values() if r['status'] == 'active']
        self.current = Snapshot(version, active, KeywordIndex(active))

    def semantic(self, snapshot):
        with self.embedding_lock:
            try:
                if snapshot.semantic is None:
                    snapshot.semantic = SemanticIndex(snapshot.records, self.encoder, self.cache_path)
                snapshot.semantic_error = False
                return snapshot.semantic
            except Exception:
                snapshot.semantic_error = True
                raise

    def submit(self, request, role):
        with self.lock:
            if any(j['status'] in ('queued', 'building') for j in self.jobs.values()):
                raise Conflict('An ingestion job is already running.')
            if request.expected_index_version != self.current.version:
                raise Conflict('Index version changed; reload before editing.')
            changes = {}
            for change in request.changes:
                record_id = change.record.id
                if record_id in changes:
                    raise Conflict('Duplicate source IDs in batch.')
                old = self.all_records.get(record_id)
                actual = old['version'] if old else 0
                if change.expected_version != actual:
                    raise Conflict('Source version changed; reload before editing.')
                # Imported public suggestions keep their original trust tier.
                if old and old.get('provenance') == 'public_origin_unverified' and change.record.provenance != 'public_origin_unverified':
                    raise Conflict('Public unverified origin must be preserved.')
                updated = change.record.versioned(actual + 1)
                if old and old.get('provenance') == 'public_origin_unverified':
                    # Editing response text must not erase attribution or original source labels.
                    for field in ('source_url','creator','license','source_row','source_labels'):
                        if field in old:
                            updated[field] = old[field]
                changes[record_id] = updated
            job_id = 'job-' + uuid4().hex  # Persisted case links cannot collide after a restart.
            self.jobs[job_id] = {'id':job_id, 'status':'queued', 'base_version':self.current.version}
            self.executor.submit(self._build, job_id, changes, role)
            return dict(self.jobs[job_id])

    def _build(self, job_id, changes, role):
        try:
            with self.lock:
                self.jobs[job_id]['status'] = 'building'
                merged = dict(self.all_records)
                merged.update(changes)
                version = self.current.version + 1
            active = [r for r in merged.values() if r['status'] == 'active']
            # Build outside the publication lock. Readers retain the previous snapshot.
            semantic = SemanticIndex(active, self.encoder, self.cache_path)
            replacement = Snapshot(version, active, KeywordIndex(active), semantic)
            with self.lock:
                overrides = {**self.overrides, **changes}
                entry = {'index_version':version, 'role':role,
                         'at':datetime.now(timezone.utc).isoformat(),
                         'sources':[{'id':r['id'], 'version':r['version'], 'status':r['status']} for r in changes.values()]}
                audit = self.audit + [entry]
                history = dict(self.history)
                for record in changes.values():
                    history[f"{record['id']}:{record['version']}"] = record
                if self.state_path:
                    self.state_path.parent.mkdir(parents=True, exist_ok=True)
                    temporary = self.state_path.with_suffix('.tmp')
                    temporary.write_text(json.dumps({'index_version':version, 'overrides':overrides, 'audit':audit, 'history':history},indent=2),encoding='utf-8')
                    temporary.replace(self.state_path)
                self.overrides, self.audit, self.all_records = overrides, audit, merged
                self.history = history
                self.current = replacement
                self.jobs[job_id].update(status='published', index_version=version)
        except Exception:
            with self.lock:
                self.jobs[job_id].update(status='failed', error='Index preparation failed; previous evidence remains active.')

    def job(self, job_id):
        with self.lock:
            return dict(self.jobs[job_id]) if job_id in self.jobs else None

    def close(self):
        self.executor.shutdown(wait=True)
