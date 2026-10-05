"""HTTP boundary for the dashboard; no retrieval or provider logic here."""
import os
from urllib.parse import quote
import httpx


class DashboardError(RuntimeError):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


class DashboardClient:
    def __init__(self, key='', transport=None):
        self.url = os.getenv('TELEASSIST_API_URL', 'http://127.0.0.1:8000').rstrip('/')
        self.editor_url = os.getenv('TELEASSIST_EDITOR_URL', self.url).rstrip('/')
        self.key, self.transport = key, transport

    def request(self, path, payload=None, *, editor=False):
        headers = {'X-API-Key': self.key} if self.key else {}
        try:
            with httpx.Client(base_url=self.editor_url if editor else self.url,
                              headers=headers, timeout=180, transport=self.transport,
                              follow_redirects=False) as client:
                response = client.request('POST' if payload is not None else 'GET',
                                          path, json=payload)
            if not response.is_success:
                try:
                    detail = response.json().get('detail')
                except (ValueError, AttributeError):
                    detail = None
                messages = {401:'Access rejected. Check your application access key.',
                            403:'Editor access is required for this operation.',
                            409:'Evidence changed. Refresh the version and review before retrying.'}
                message = messages.get(response.status_code)
                if not message:
                    message = detail if isinstance(detail, str) else f'API request failed ({response.status_code}). Check the submitted fields.'
                raise DashboardError(message, response.status_code)
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError('Expected an object.')
            return data
        except httpx.TimeoutException:
            raise DashboardError('The API timed out. Check service/job status before retrying; a submitted update may still be running.') from None
        except httpx.HTTPError:
            raise DashboardError('Cannot reach the API. Start the backend and check its configured address.') from None
        except ValueError:
            raise DashboardError('The API returned an invalid response.') from None

    def source(self, source_id, version=None):
        path = '/sources/' + quote(source_id, safe='')
        return self.request(path + (f'?version={version}' if version is not None else ''))
