"""Explicit free-plan provider configuration; bounded retries and no paid fallback."""
import json
import os
from pathlib import Path
import threading
import time
import httpx


class ProviderUnavailable(RuntimeError):
    pass


def load_environment(path='.env'):
    # Small dependency-free dotenv reader; never print key values.
    path = Path(path)
    if path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            if line.strip() and not line.lstrip().startswith('#') and '=' in line:
                name, value = line.split('=', 1)
                os.environ.setdefault(name.strip(), value.strip().strip('\"\''))


class FreeLLM:
    def __init__(self, transport=None, sleeper=time.sleep):
        load_environment()
        self.provider = os.getenv('LLM_PROVIDER', 'gemini')
        self.model = os.getenv('LLM_MODEL', 'openai/gpt-oss-20b' if self.provider == 'groq' else 'gemini-3.5-flash-lite')
        self.key = os.getenv('GROQ_API_KEY' if self.provider == 'groq' else 'GEMINI_API_KEY', '')
        self.confirmed_free = os.getenv('LLM_FREE_PLAN_CONFIRMED', '').lower() == 'true'
        self.transport = transport
        self.sleep = sleeper
        self.lock = threading.Lock()
        self.last_call = 0.0
        self.interval = float(os.getenv('LLM_MIN_INTERVAL_SECONDS', '15'))
        self.capture_path = None  # Set only by synthetic-corpus generation, never resolve.

    @property
    def configured(self):
        allowed = {'gemini': {'gemini-3.8-flash', 'gemini-3.5-flash-lite', 'gemini-3.1-flash-lite', 'gemini-3-flash-preview'},
                   'groq': {'openai/gpt-oss-20b', 'openai/gpt-oss-120b'}}
        return bool(self.key and self.confirmed_free and self.model in allowed.get(self.provider, set()))

    def generate(self, system, payload, max_tokens=4000):
        if not self.configured:
            raise ProviderUnavailable('Configure a confirmed free-plan provider locally.')
        with self.lock:
            delay = self.interval - (time.monotonic() - self.last_call)
            if delay > 0:
                self.sleep(delay)
            if self.provider == 'groq':
                url = 'https://api.groq.com/openai/v1/chat/completions'
                headers = {'Authorization': 'Bearer ' + self.key}
                body = {'model': self.model, 'temperature': 0.2, 'max_tokens': max_tokens,
                        'response_format': {'type': 'json_object'},
                        'messages': [{'role': 'system', 'content': system},
                                     {'role': 'user', 'content': json.dumps(payload)}]}
            else:
                url = f'https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent'
                headers = {'x-goog-api-key': self.key}
                body = {'systemInstruction': {'parts': [{'text': system}]},
                        'contents': [{'parts': [{'text': json.dumps(payload)}]}],
                        'generationConfig': {'temperature': 0.2, 'maxOutputTokens': max_tokens,
                                             'responseMimeType': 'application/json'}}
                if payload.get('schema') and not payload.get('output_key'):
                    body['generationConfig']['responseJsonSchema'] = payload['schema']
            with httpx.Client(timeout=90, transport=self.transport) as client:
                for attempt in range(3):
                    self.last_call = time.monotonic()
                    try:
                        response = client.post(url, headers=headers, json=body)
                    except httpx.HTTPError:
                        raise ProviderUnavailable('Provider connection failed.') from None
                    if response.status_code == 429 or response.status_code >= 500:
                        if attempt == 2:
                            raise ProviderUnavailable('Provider quota or availability limit reached.')
                        try:
                            delay = min(60, max(self.interval, float(response.headers.get('retry-after', 2 ** (attempt + 1)))))
                        except ValueError:
                            delay = max(self.interval, 2 ** (attempt + 1))
                        self.sleep(delay)
                        continue
                    if response.status_code != 200:
                        raise ProviderUnavailable(f'Provider rejected the request (HTTP {response.status_code}).')
                    try:
                        data = response.json()
                        if self.capture_path:
                            Path(self.capture_path).write_text(json.dumps(data, indent=2), encoding='utf-8')
                        if self.provider == 'groq':
                            text = data['choices'][0]['message']['content']
                            finish = data['choices'][0].get('finish_reason', 'unknown')
                        else:
                            candidate = data['candidates'][0]
                            text = ''.join(part.get('text', '') for part in candidate['content']['parts'] if not part.get('thought'))
                            finish = candidate.get('finishReason', 'unknown')
                        text = text.strip()
                        if text.startswith('```'):
                            text = text.split('\n', 1)[1].rsplit('```', 1)[0].strip()
                        if finish in ('MAX_TOKENS', 'length'):
                            raise ProviderUnavailable('Provider output was truncated; increase output budget or shorten batch records.')
                        result = json.loads(text)
                        if isinstance(result, list) and payload.get('output_key'):
                            result = {payload['output_key']: result}
                        if not isinstance(result, dict):
                            raise ValueError('Expected object.')
                        return result
                    except (ValueError, KeyError, IndexError, TypeError) as error:
                        raise ProviderUnavailable(f'Provider returned invalid structured output ({type(error).__name__}).') from None
        raise ProviderUnavailable('Provider unavailable.')
