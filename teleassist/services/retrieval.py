"""Standalone retrieval/evidence service, sharing the same tested implementation."""
from teleassist.services.combined import create_app
from teleassist.common.paths import runtime_paths


class NoGeneration:
    configured = False


def create_retrieval_app(**kwargs):
    kwargs.setdefault('provider',NoGeneration())
    app = create_app(**kwargs)
    app.title = 'TeleAssist retrieval and evidence updates'
    app.router.routes = [route for route in app.router.routes if getattr(route,'path',None) != '/resolve']
    return app


app = create_retrieval_app(**runtime_paths())
