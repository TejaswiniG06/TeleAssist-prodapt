"""Conservative pattern masking before retrieval or external calls; no raw-text logging."""
import re

PATTERNS = [
    ('EMAIL', r'\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b'),
    ('IP_ADDRESS', r'\b(?:\d{1,3}\.){3}\d{1,3}\b'),
    ('SECRET', r'(?i)\b(?:password|otp|pin|api[_ -]?key)\s*(?:is|:|=)\s*\S+'),
    ('ACCOUNT', r'(?i)\b(?:account|customer|subscriber)\s*(?:number|id|no\.?)\s*(?:(?:is|:|=)\s*[A-Z0-9-]{5,}|(?=[A-Z0-9-]*\d)[A-Z0-9-]{5,})'),
    ('PHONE', r'(?<!\w)(?:\+?\d[\d ()-]{7,}\d)(?!\w)'),
]


def mask(text):
    counts = {}
    for name, pattern in PATTERNS:
        text, count = re.subn(pattern, '[' + name + ']', text)
        if count:
            counts[name] = counts.get(name, 0) + count
    return text, counts
