"""Conservative pattern masking before retrieval or external calls; no raw-text logging."""
import re

PATTERNS = [
    ('EMAIL', r'\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b'),
    ('SECRET', r'\b(?:AIza[0-9A-Za-z_-]{30,}|gsk_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,})\b'),
    ('NAME', r'(?i)\b(?:my name is|customer name\s*[:=]|subscriber name\s*[:=])\s+[A-Za-z][A-Za-z\x27-]*(?:\s+[A-Za-z][A-Za-z\x27-]*){0,2}'),
    ('ADDRESS', r'(?i)\b(?:my address is|street address\s*[:=])\s+[^\n.!?]{5,150}'),
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
