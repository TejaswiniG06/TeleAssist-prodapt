"""Standalone retrieval/evidence service, sharing the same tested implementation."""
from pathlib import Path
from api import create_app
from llm import load_environment


class NoGeneration:
    configured = False


def create_retrieval_app(**kwargs):
    kwargs.setdefault('provider',NoGeneration())
    app = create_app(**kwargs)
    app.title = 'TeleAssist retrieval and evidence updates'
    app.router.routes = [route for route in app.router.routes if getattr(route,'path',None) != '/resolve']
    return app


load_environment()
ROOT = Path(__file__).parent
app = create_retrieval_app(cache_path=ROOT/'runtime/embeddings.json',
                           state_path=ROOT/'runtime/evidence_state.json',topic_path=ROOT/'runtime/topic_state.json')
