import os
import unittest
from unittest.mock import patch
import httpx
from teleassist.resolution.llm import FreeLLM, ProviderUnavailable


class ProviderTests(unittest.TestCase):
    def test_rate_limit_retry_and_json_response(self):
        calls = []
        waits = []
        def respond(request):
            calls.append(request)
            if len(calls) == 1:
                return httpx.Response(429, headers={'retry-after': '2'})
            return httpx.Response(200, json={'candidates': [{'content': {'parts': [{'text': '{"status":"ok"}'}]}}]})
        with patch.dict(os.environ, {'LLM_PROVIDER': 'gemini', 'GEMINI_API_KEY': 'test-secret',
                                    'LLM_FREE_PLAN_CONFIRMED': 'true', 'LLM_MIN_INTERVAL_SECONDS': '0'}):
            provider = FreeLLM(transport=httpx.MockTransport(respond), sleeper=waits.append)
            self.assertEqual(provider.generate('Return JSON', {}), {'status': 'ok'})
        self.assertEqual(len(calls), 2)
        self.assertEqual(waits, [2])
        self.assertEqual(calls[0].headers['x-goog-api-key'], 'test-secret')

    def test_missing_or_unconfirmed_key_makes_no_calls(self):
        with patch.dict(os.environ, {'LLM_PROVIDER': 'gemini', 'GEMINI_API_KEY': '', 'LLM_FREE_PLAN_CONFIRMED': 'false'}):
            provider = FreeLLM()
            with self.assertRaises(ProviderUnavailable):
                provider.generate('Return JSON', {})

    def test_error_does_not_expose_provider_body(self):
        def respond(request):
            return httpx.Response(403, json={'error': {'message': 'test-secret'}})
        with patch.dict(os.environ, {'LLM_PROVIDER': 'gemini', 'GEMINI_API_KEY': 'test-secret', 'LLM_FREE_PLAN_CONFIRMED': 'true'}):
            provider = FreeLLM(transport=httpx.MockTransport(respond))
            with self.assertRaises(ProviderUnavailable) as caught:
                provider.generate('Return JSON', {})
            self.assertNotIn('test-secret', str(caught.exception))
