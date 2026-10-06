"""Local startup refuses busy ports and stops its owned process tree."""
import socket
from contextlib import closing
import subprocess
import sys
import unittest
from unittest.mock import patch
import httpx
import psutil
from start import available, stop_process, warm_search


class StartupTests(unittest.TestCase):
    def test_semantic_warmup_sends_application_key_and_checks_readiness(self):
        requests = []
        def handle(request):
            requests.append(request)
            return httpx.Response(200, json={})
        with closing(httpx.Client(transport=httpx.MockTransport(handle))) as client:
            with patch('start.httpx.Client', return_value=client):
                warm_search('http://retrieval', 'test-application-key')
        self.assertEqual([r.url.path for r in requests], ['/search', '/ready'])
        self.assertEqual(requests[0].headers['X-API-Key'], 'test-application-key')
        self.assertEqual(requests[1].url.params['require_semantic'], 'true')

    def test_warmup_access_errors_do_not_blame_model_download(self):
        for status in (401, 403):
            with self.subTest(status=status):
                with closing(httpx.Client(transport=httpx.MockTransport(
                    lambda request: httpx.Response(status)
                ))) as client:
                    with patch('start.httpx.Client', return_value=client):
                        with self.assertRaisesRegex(RuntimeError, 'access was denied') as error:
                            warm_search('http://retrieval', 'secret-application-key')
                self.assertNotIn('--skip-warmup', str(error.exception))
                self.assertNotIn('secret-application-key', str(error.exception))

    def test_unavailable_model_and_readiness_offer_skip_warmup(self):
        for failed_path in ('/search', '/ready'):
            with self.subTest(failed_path=failed_path):
                with closing(httpx.Client(transport=httpx.MockTransport(
                    lambda request: httpx.Response(503 if request.url.path == failed_path else 200)
                ))) as client:
                    with patch('start.httpx.Client', return_value=client):
                        with self.assertRaisesRegex(RuntimeError, '--skip-warmup'):
                            warm_search('http://retrieval')

    def test_warmup_timeout_has_recovery_command_without_leaking_details(self):
        def timeout(request):
            raise httpx.ReadTimeout('private transport detail', request=request)
        with closing(httpx.Client(transport=httpx.MockTransport(timeout))) as client:
            with patch('start.httpx.Client', return_value=client):
                with self.assertRaisesRegex(RuntimeError, 'timed out') as error:
                    warm_search('http://retrieval')
        self.assertIn('--skip-warmup', str(error.exception))
        self.assertNotIn('private transport detail', str(error.exception))

    def test_warmup_transport_and_other_http_errors_have_distinct_messages(self):
        def disconnected(request):
            raise httpx.ConnectError('private connection detail', request=request)
        for handler, message in (
            (disconnected, 'Could not reach retrieval'),
            (lambda request: httpx.Response(500), 'HTTP 500'),
        ):
            with closing(httpx.Client(transport=httpx.MockTransport(handler))) as client:
                with patch('start.httpx.Client', return_value=client):
                    with self.assertRaisesRegex(RuntimeError, message):
                        warm_search('http://retrieval')

    def test_busy_port_is_rejected_without_stopping_the_existing_listener(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen()
            with self.assertRaisesRegex(RuntimeError, 'already in use'):
                available(listener.getsockname()[1])
            self.assertGreater(listener.fileno(), -1)

    def test_shutdown_stops_children_of_the_python_launcher(self):
        command = ('import subprocess,sys,time; '
                   'child=subprocess.Popen([sys.executable,"-c","import time;time.sleep(90)"]); '
                   'print(child.pid,flush=True);time.sleep(90)')
        child = subprocess.Popen([sys.executable, '-c', command], stdout=subprocess.PIPE, text=True)
        try:
            grandchild = int(child.stdout.readline().strip())
            self.assertTrue(psutil.pid_exists(grandchild))
            stop_process(child)
            self.assertIsNotNone(child.poll())
            self.assertFalse(psutil.pid_exists(grandchild))
        finally:
            stop_process(child)
            child.stdout.close()
