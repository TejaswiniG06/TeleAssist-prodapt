"""Saved cases are operational records; only reviewed outcomes become evidence."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from threading import RLock
from typing import Literal
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field, model_validator
from privacy import mask
from resolution import Classification, canonical_action
from catalog import EvidenceRecord, Conflict


def now():
    return datetime.now(timezone.utc).isoformat()


def scrub(value):
    if isinstance(value, str):
        return mask(value)[0]
    if isinstance(value, list):
        return [scrub(item) for item in value]
    if isinstance(value, dict):
        return {key: scrub(item) for key, item in value.items()}
    return value


class SavedCitation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')
    version: int = Field(ge=1)


class DraftSnapshot(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: Literal['resolution', 'clarification', 'escalation']
    answer: str = Field(max_length=12000)
    classification: Classification
    citations: list[SavedCitation] = Field(default_factory=list, max_length=20)


class CaseCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    complaint: str = Field(min_length=1, max_length=5000)
    observations: str = Field(default='', max_length=3000)
    draft: DraftSnapshot

    @model_validator(mode='after')
    def nonblank(self):
        if not self.complaint.strip():
            raise ValueError('Complaint must not be blank.')
        return self


class CaseOutcome(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_revision: int = Field(ge=1)
    outcome: Literal['resolved', 'not_resolved']
    actual_actions: list[str] = Field(default_factory=list, max_length=20)
    outcome_evidence: str = Field(min_length=10, max_length=2000)
    confirmed: Literal[True]

    @model_validator(mode='after')
    def actual_steps(self):
        if len(self.outcome_evidence.strip()) < 10:
            raise ValueError('Describe the actual observed outcome.')
        if self.outcome == 'resolved' and not self.actual_actions:
            raise ValueError('Resolved outcomes need actions actually performed.')
        if any(not 10 <= len(action.strip()) <= 1500 for action in self.actual_actions):
            raise ValueError('Each actual action must contain 10–1500 characters.')
        return self


class CaseReview(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_revision: int = Field(ge=1)
    decision: Literal['approve', 'reject']
    rationale: str = Field(min_length=10, max_length=1000)
    confirmed: Literal[True]
    expected_index_version: int | None = Field(default=None, ge=1)
    title: str = Field(default='', max_length=250)
    product: Literal['broadband', 'mobile', 'fixed_voice', 'iptv', 'unknown'] = 'unknown'
    category: str = Field(default='unknown', pattern=r'^[a-z][a-z0-9_]{0,79}$')
    applicability: str = Field(default='', max_length=1500)

    @model_validator(mode='after')
    def complete_review(self):
        if len(self.rationale.strip()) < 10:
            raise ValueError('Supply a review rationale.')
        if self.decision == 'approve' and (self.expected_index_version is None or
                len(self.title.strip()) < 3 or self.product == 'unknown' or
                len(self.applicability.strip()) < 5):
            raise ValueError('Publication requires index version, title, known product and applicability.')
        return self


class CaseStore:
    """Small transactional SQLite ledger with optimistic revisions and masked text."""
    def __init__(self, path=None):
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()
        self.db = sqlite3.connect(str(path) if path else ':memory:', check_same_thread=False)
        self.db.execute('CREATE TABLE IF NOT EXISTS cases '
                        '(id TEXT PRIMARY KEY, request_id TEXT UNIQUE, data TEXT NOT NULL)')
        self.db.commit()

    def _write(self, case):
        # Write before exposing the new state; SQLite commits or rolls back as a unit.
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO cases VALUES (?, ?, ?)',
                            (case['id'], case['request_id'], json.dumps(case)))
        return case

    def get(self, case_id):
        with self.lock:
            row = self.db.execute('SELECT data FROM cases WHERE id=?', (case_id,)).fetchone()
            if not row:
                raise KeyError(case_id)
            return json.loads(row[0])

    def list(self, limit=50):
        with self.lock:
            rows = self.db.execute('SELECT data FROM cases ORDER BY rowid DESC LIMIT ?', (limit,)).fetchall()
            return [json.loads(row[0]) for row in rows]

    def save(self, request, role):
        payload = scrub(request.model_dump())
        with self.lock:
            existing = self.db.execute('SELECT data FROM cases WHERE request_id=?',
                                       (request.request_id,)).fetchone()
            if existing:
                case = json.loads(existing[0])
                if any(case[field] != payload[field] for field in payload):
                    raise Conflict('Save request already exists with different content.')
                return case  # Safe retry after a lost response, without duplicate cases.
            case = dict(payload, id='case-' + uuid4().hex, revision=1, status='pending',
                        created_at=now(), updated_at=now(), outcome=None, review=None,
                        publication=None, events=[{'event':'saved', 'role':role, 'at':now()}])
            return self._write(case)

    def _editable(self, case_id, revision):
        case = self.get(case_id)
        if case['revision'] != revision:
            raise Conflict('Case changed; reload before editing.')
        if case['status'] in ('publishing', 'published'):
            raise Conflict('A publishing/published case cannot be changed.')
        return case

    def _change(self, case, event, role):
        case['revision'] += 1
        case['updated_at'] = now()
        case['events'].append({'event':event, 'role':role, 'at':now()})
        return self._write(case)

    def record_outcome(self, case_id, request, role):
        with self.lock:
            case = self._editable(case_id, request.expected_revision)
            case['outcome'] = scrub(request.model_dump(exclude={'expected_revision'}))
            case.update(status='outcome_recorded', review=None, publication=None)
            return self._change(case, 'outcome_recorded', role)

    def review(self, case_id, request, role):
        with self.lock:
            case = self._editable(case_id, request.expected_revision)
            if case['status'] != 'outcome_recorded':
                raise Conflict('Record an actual outcome before review.')
            case['review'] = scrub(request.model_dump(exclude={'expected_revision'}))
            if request.decision == 'reject':
                case['status'] = 'rejected'
            else:
                record = self.evidence(case, CaseReview.model_validate(scrub(request.model_dump())))
                case['status'] = 'publishing'
                case['publication'] = {'source_id':record.id, 'job_id':None,
                                       'record':record.model_dump(), 'error':None}
            return self._change(case, 'review_' + request.decision, role)

    @staticmethod
    def evidence(case, review):
        outcome = case['outcome']
        resolved = outcome['outcome'] == 'resolved'
        return EvidenceRecord(id='HISTORY-' + case['id'][5:], title=review.title,
            product=review.product, category=review.category, provenance='reviewed_internal',
            record_type='resolved_ticket' if resolved else 'unresolved_ticket',
            complaint=case['complaint'], observations=[case['observations']] if case['observations'] else [],
            applicability=review.applicability, outcome=outcome['outcome'],
            outcome_evidence=outcome['outcome_evidence'],
            resolution_steps=[{'action_id':canonical_action('case_step_' + str(i), instruction) + '_' + str(i),
                               'instruction':instruction, 'condition':review.applicability}
                              for i, instruction in enumerate(outcome['actual_actions'], 1)] if resolved else [],
            suggested_steps='\n'.join(outcome['actual_actions']) if not resolved else '')

    def attach_job(self, case_id, job_id):
        with self.lock:
            case = self.get(case_id)
            case['publication']['job_id'] = job_id
            return self._write(case)

    def refresh(self, case_id, catalog):
        # Reconcile publication using durable evidence, even if a restart lost job state.
        with self.lock:
            case = self.get(case_id)
            if case['status'] != 'publishing':
                return case
            publication = case['publication']
            with catalog.lock:
                source = catalog.history.get(publication['source_id'] + ':1')
            if source:
                expected = scrub(publication['record'])
                if any(source.get(key) != value for key, value in expected.items()):
                    raise Conflict('Published source differs from the reviewed case; inspect evidence history.')
                case['status'] = 'published'
                publication['source_version'] = 1
                return self._change(case, 'published', 'system')
            job = catalog.job(publication['job_id']) if publication['job_id'] else None
            if job and job['status'] in ('queued', 'building'):
                return case
            return self.publication_failed(case_id)

    def publication_failed(self, case_id):
        with self.lock:
            case = self.get(case_id)
            case['status'] = 'outcome_recorded'
            case['publication']['error'] = 'Publication did not complete. Review and retry using the current index version.'
            return self._change(case, 'publication_failed', 'system')

    def close(self):
        self.db.close()
