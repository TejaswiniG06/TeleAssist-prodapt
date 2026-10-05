"""Shared storage configuration; only the retrieval process writes in split mode."""
import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def runtime_paths():
    from teleassist.resolution.llm import load_environment
    load_environment(PROJECT_ROOT / '.env')
    root = Path(os.getenv('TELEASSIST_STATE_DIR', str(PROJECT_ROOT / 'runtime')))
    return {'cache_path': root / 'embeddings.json', 'case_path': root / 'cases.sqlite3',
            'state_path': root / 'evidence_state.json', 'topic_path': root / 'topic_state.json'}
