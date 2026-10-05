"""Build a bounded retrieval query from existing classification; no model calls."""
from teleassist.common.privacy import mask


def build_search_query(complaint, classification=None, mode='enriched', limit=2000):
    if mode not in ('raw','enriched'):
        raise ValueError('Query mode must be raw or enriched.')
    raw = mask(complaint)[0]
    if mode == 'raw' or not classification:
        return raw[:limit]
    values = []
    for field in ('product','category'):
        value = classification.get(field, 'unknown')
        if value and value != 'unknown':
            values.append(value.replace('_', ' '))
    values.extend(classification.get('symptoms', []))
    values.extend(a['action_id'].replace('_', ' ') for a in classification.get('attempted_actions', []))
    # Keep raw language, omit sentiment/severity/churn, and avoid repeated metadata terms.
    normalized = list(dict.fromkeys(mask(value.strip())[0] for value in values if value.strip()))
    if not normalized:
        return raw[:limit]
    extra = '\n' + '; '.join(normalized)[:600]
    return raw[:limit-len(extra)] + extra
