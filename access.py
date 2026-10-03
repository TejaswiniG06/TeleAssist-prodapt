"""Small role-based API-key policy for a local prototype."""
import os
import secrets
from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader

key_header = APIKeyHeader(name='X-API-Key', auto_error=False)


class AccessPolicy:
    def __init__(self, mode='local', agent_key='', editor_key=''):
        if mode not in ('local', 'required'):
            raise ValueError('AUTH_MODE must be local or required.')
        if mode == 'required' and (not agent_key or not editor_key):
            raise ValueError('Required authentication needs separate agent and editor keys.')
        if agent_key and editor_key and secrets.compare_digest(agent_key.encode(), editor_key.encode()):
            raise ValueError('Agent and editor keys must differ.')
        self.mode, self.agent_key, self.editor_key = mode, agent_key, editor_key

    @classmethod
    def from_environment(cls):
        return cls(os.getenv('AUTH_MODE', 'local'), os.getenv('TELEASSIST_AGENT_KEY', ''),
                   os.getenv('TELEASSIST_EDITOR_KEY', ''))

    def agent(self, key: str | None = Depends(key_header)):
        if key and self.editor_key and secrets.compare_digest(key.encode(), self.editor_key.encode()):
            return 'editor'
        if key and self.agent_key and secrets.compare_digest(key.encode(), self.agent_key.encode()):
            return 'agent'
        if not key and self.mode == 'local':
            return 'local_agent'
        raise HTTPException(401, 'A valid X-API-Key is required.')

    def editor(self, key: str | None = Depends(key_header)):
        if not self.editor_key:
            raise HTTPException(503, 'Editor access is not configured.')
        if self.agent(key) != 'editor':
            raise HTTPException(403, 'Editor role required.')
        return 'editor'
