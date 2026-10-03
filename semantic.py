"""Local sentence embeddings and reciprocal-rank fusion; no hosted API."""
import hashlib
import json
import math
from pathlib import Path
from retrieval import KeywordIndex, searchable_text

MODEL = 'sentence-transformers/all-MiniLM-L6-v2'


class LocalEncoder:
    def __init__(self):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(MODEL, device='cpu',
                                         cache_folder=str(Path(__file__).parent / 'runtime' / 'huggingface' / 'hub'))

    def encode(self, texts):
        return self.model.encode(texts, normalize_embeddings=True).tolist()


def normalize(vector):
    norm = math.sqrt(sum(v * v for v in vector))
    if not norm or not math.isfinite(norm):
        raise ValueError('Embedding must have a finite nonzero norm.')
    return [v / norm for v in vector]


class SemanticIndex:
    def __init__(self, records, encoder=None, cache_path=None, model_key=MODEL):
        self.records = [r for r in records if r['status'] == 'active']
        self.encoder = encoder or LocalEncoder()
        cache = {}
        if cache_path and Path(cache_path).exists():
            try:
                cache = json.loads(Path(cache_path).read_text(encoding='utf-8'))
            except (ValueError, OSError):
                cache = {}
        texts = [searchable_text(r) for r in self.records]
        keys = [hashlib.sha256((model_key + '\n' + t).encode()).hexdigest() for t in texts]
        missing = list(dict.fromkeys(k for k in keys if k not in cache))
        by_key = dict(zip(keys, texts))
        if missing:
            vectors = self.encoder.encode([by_key[k] for k in missing])
            if len(vectors) != len(missing):
                raise ValueError('Encoder returned an incorrect number of vectors.')
            cache.update({k: normalize(v) for k, v in zip(missing, vectors)})
        self.vectors = [normalize(cache[k]) for k in keys]
        if len({len(v) for v in self.vectors}) > 1:
            raise ValueError('Embedding dimensions differ.')
        if cache_path:
            path = Path(cache_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix('.tmp')
            temporary.write_text(json.dumps({k: cache[k] for k in keys}), encoding='utf-8')
            temporary.replace(path)

    def search(self, query, limit=4, min_score=0.30, allowed_ids=None):
        if not query.strip() or not 1 <= limit <= 20:
            raise ValueError('Query must be nonempty and limit between 1 and 20.')
        if not 0 <= min_score <= 1:
            raise ValueError('Minimum cosine score must be between zero and one.')
        if not self.records:
            return []
        vector = normalize(self.encoder.encode([query])[0])
        if len(vector) != len(self.vectors[0]):
            raise ValueError('Query embedding dimension differs.')
        results = []
        for record, embedding in zip(self.records, self.vectors):
            if allowed_ids is not None and record['id'] not in allowed_ids:
                continue
            score = sum(a * b for a, b in zip(vector, embedding))
            if score >= min_score:
                results.append(dict(id=record['id'], version=record['version'],
                                    score=round(score, 6), record=record))
        return sorted(results, key=lambda r: (-r['score'], r['id']))[:limit]


class HybridIndex:
    def __init__(self, keyword, semantic):
        self.keyword = keyword
        self.semantic = semantic

    def search(self, query, limit=4, min_score=0.30, allowed_ids=None):
        if not query.strip() or not 1 <= limit <= 20:
            raise ValueError('Query must be nonempty and limit between 1 and 20.')
        combined = {}
        keyword = self.keyword
        if allowed_ids is not None:
            keyword = KeywordIndex([r for r in keyword.records if r['id'] in allowed_ids])
        for name, hits in [('keyword', keyword.search(query, 20)),
                           ('semantic', self.semantic.search(query, 20, min_score, allowed_ids))]:
            for rank, hit in enumerate(hits, 1):
                result = combined.setdefault(hit['id'], dict(hit, score=0.0, components={}))
                result['score'] += 1 / (60 + rank)
                result['components'][name] = dict(rank=rank, score=hit['score'])
        return sorted(combined.values(), key=lambda r: (-r['score'], r['id']))[:limit]
