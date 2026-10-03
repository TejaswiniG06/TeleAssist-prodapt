"""Group masked weak-match complaints; only editor review changes taxonomy."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from threading import Lock
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from privacy import mask
from resolution import SUSPICIOUS


class TopicReview(BaseModel):
    model_config = ConfigDict(extra='forbid')
    decision: Literal['approve', 'reject']
    category: str = Field(default='', pattern=r'^(?:[a-z][a-z0-9_]{2,79})?$')
    rationale: str = Field(min_length=10, max_length=1000)


class ReplayRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    complaints: list[str] = Field(min_length=1, max_length=50)


class TopicMonitor:
    def __init__(self, categories, path=None, similarity=.35, min_cluster=3):
        self.lock = Lock()
        self.path = Path(path) if path else None
        self.similarity, self.min_cluster = similarity, min_cluster
        self.categories = set(categories) | {'unknown'}
        self.samples, self.reviews = {}, {}
        self.storage_error = False
        if self.path and self.path.exists():
            data = json.loads(self.path.read_text(encoding='utf-8'))
            self.samples, self.reviews = data['samples'], data['reviews']
        self.proposals = []
        self._group()

    def _save(self):
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix('.tmp')
            temporary.write_text(json.dumps({'samples':self.samples,'reviews':self.reviews},indent=2),encoding='utf-8')
            temporary.replace(self.path)
        self.storage_error = False

    def observe(self, text, index_version, reason):
        text = mask(text.strip())[0]
        if len(text) < 10 or SUSPICIOUS.search(text):
            return False
        digest = hashlib.sha256(text.lower().encode()).hexdigest()[:24]
        with self.lock:
            if digest in self.samples:
                self.samples[digest]['occurrences'] += 1
            else:
                self.samples[digest] = {'id':digest,'text':text[:2000], 'index_version':index_version,
                                        'reason':reason,'occurrences':1}
                if len(self.samples) > 200:
                    del self.samples[next(iter(self.samples))]
            self._group()
            # Monitoring failure must not turn a valid search into an outage.
            try:
                self._save()
            except OSError:
                self.storage_error = True
            return True

    def _group(self):
        rows = list(self.samples.values())
        self.proposals = []
        if len(rows) < self.min_cluster:
            return
        vectorizer = TfidfVectorizer(stop_words='english',ngram_range=(1,2),max_features=2000)
        try:
            vectors = vectorizer.fit_transform([r['text'] for r in rows])
        except ValueError:
            return
        similarities = cosine_similarity(vectors)
        remaining = set(range(len(rows)))
        vocabulary = vectorizer.get_feature_names_out()
        while remaining:
            cluster, pending = set(), [min(remaining)]
            while pending:
                index = pending.pop()
                if index not in remaining:
                    continue
                remaining.remove(index)
                cluster.add(index)
                pending.extend(i for i in sorted(remaining) if similarities[index,i] >= self.similarity)
            if len(cluster) < self.min_cluster:
                continue
            members = [rows[i] for i in sorted(cluster)]
            topic_id = 'topic-' + hashlib.sha256('|'.join(sorted(r['id'] for r in members)).encode()).hexdigest()[:16]
            average = vectors[sorted(cluster)].mean(axis=0).A1
            terms = [vocabulary[i] for i in average.argsort()[::-1][:5] if average[i] > 0]
            review = self.reviews.get(topic_id)
            self.proposals.append({'id':topic_id,'suggested_terms':terms,'distinct_complaints':len(members),
                                   'occurrences':sum(r['occurrences'] for r in members),
                                   'examples':[r['text'] for r in members[:3]],
                                   'status':{'approve':'approved','reject':'rejected'}[review['decision']] if review else 'pending',
                                   'review':review, 'member_ids':[r['id'] for r in members]})

    def taxonomy(self):
        with self.lock:
            return sorted(self.categories | {r['category'] for r in self.reviews.values() if r['decision']=='approve'})

    def report(self):
        with self.lock:
            return {'buffered_distinct_complaints':len(self.samples),'proposals':json.loads(json.dumps(self.proposals)),
                    'similarity_threshold':self.similarity,'min_cluster':self.min_cluster,
                    'storage_state':'degraded' if self.storage_error else 'ok',
                    'notice':'Weak matches and lexical clusters are review signals, not proof of a new telecom fault or approved fixes.'}

    def review(self, topic_id, request, role):
        with self.lock:
            if not any(p['id']==topic_id for p in self.proposals):
                raise KeyError('Topic not found; reload proposals.')
            if topic_id in self.reviews:
                raise ValueError('Topic already reviewed.')
            if request.decision == 'approve' and (not request.category or request.category in self.categories or
                    any(r['category']==request.category for r in self.reviews.values() if r['decision']=='approve')):
                raise ValueError('Approval needs a new, unique category name.')
            review = {'decision':request.decision,'category':request.category if request.decision=='approve' else '',
                      'rationale':mask(request.rationale)[0],'role':role,
                      'at':datetime.now(timezone.utc).isoformat()}
            self.reviews[topic_id] = review
            try:
                self._save()
            except OSError:
                del self.reviews[topic_id]
                self.storage_error = True
                raise
            self._group()
            return review
