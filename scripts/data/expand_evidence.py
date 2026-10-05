"""Idempotent, explicitly synthetic development evidence expansion."""
from teleassist.common.paths import PROJECT_ROOT
import json
from pathlib import Path


def expand():
    path = PROJECT_ROOT / 'data' / 'knowledge_base.json'
    records = json.loads(path.read_text(encoding='utf-8'))
    additions = [
        ('KB-004', 'Collect observations for weak Wi-Fi coverage', 'wifi_issue', 'broadband',
         ['wireless signal weak', 'Wi-Fi dead zone', 'wired connection works'],
         [('compare_wired_connection', 'Compare Wi-Fi with an existing wired connection.', 'A wired comparison is available.'),
          ('check_router_placement', 'Ask about router placement and distance from the affected device.', 'Placement is unknown.')]),
        ('KB-005', 'Triage mobile data connectivity', 'mobile_data', 'mobile',
         ['cellular data unavailable', 'mobile internet stopped', '4G 5G data failure'],
         [('check_device_scope', 'Ask whether calls, messages, and mobile data are all affected.', 'Affected services are unknown.'),
          ('collect_signal_status', 'Record signal indication, location context, and when the issue started.', 'Signal observations are missing.')]),
        ('KB-006', 'Collect observations for calls that drop', 'voice_quality', 'mobile',
         ['phone call cuts off', 'dropped calls', 'poor voice quality'],
         [('collect_call_pattern', 'Ask whether the issue affects every call and whether it occurs in one location.', 'Call pattern is unknown.'),
          ('collect_signal_status', 'Record the signal indication during affected calls.', 'Signal observations are missing.')]),
        ('KB-007', 'Triage fixed voice service unavailability', 'fixed_voice', 'fixed_voice',
         ['VoIP no dial tone', 'landline cannot call', 'voice service offline'],
         [('check_service_scope', 'Ask whether the associated internet service also stopped.', 'Associated service status is unknown.'),
          ('collect_connection_status', 'Collect visible equipment indicators and the time service stopped.', 'Status observations are missing.')])]
    existing = {r['id'] for r in records}
    for source_id, title, category, product, symptoms, steps in additions:
        if source_id in existing:
            continue
        records.append(dict(id=source_id, record_type='article', title=title, category=category,
                            product=product, version=1, status='active', updated_at='2026-10-03',
                            provenance='synthetic_demo', evidence_level='illustrative_unapproved',
                            symptoms=symptoms, steps=[dict(action_id=a, instruction=i, condition=c) for a, i, c in steps],
                            escalation='Refer persistent issues with collected observations to authorized provider support. Do not invent a cause, policy, or restoration time.'))
    for record in records:
        record.setdefault('evidence_level', 'illustrative_unapproved')
        record.setdefault('labels', {'product': record['product'], 'category': record['category'],
                                    'severity': 'unknown', 'sentiment': 'unknown',
                                    'label_origin': 'manual_synthetic_authoring'})
    path.write_text(json.dumps(records, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    expand()
