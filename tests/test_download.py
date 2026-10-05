import hashlib
from pathlib import Path
import tempfile
import unittest
import httpx
from scripts.data.download_public import checked_download


class DownloadTests(unittest.TestCase):
    def test_checksum_failure_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'source.csv'
            path.write_bytes(b'previous data')
            transport = httpx.MockTransport(lambda request:httpx.Response(200,content=b'changed upstream'))
            with self.assertRaises(ValueError):
                checked_download(path,expected_hash=hashlib.sha256(b'expected').hexdigest(),transport=transport)
            self.assertEqual(path.read_bytes(),b'previous data')
            self.assertFalse(path.with_suffix('.download').exists())

    def test_verified_download_and_reuse(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'source.csv'
            data = b'subject,body\nrouter,offline'
            digest = hashlib.sha256(data).hexdigest()
            calls=[]
            def response(request):
                calls.append(request.url)
                return httpx.Response(200,content=data)
            transport=httpx.MockTransport(response)
            self.assertEqual(checked_download(path,expected_hash=digest,transport=transport),'downloaded_and_verified')
            self.assertEqual(checked_download(path,expected_hash=digest,transport=transport),'existing_verified_file')
            self.assertEqual(len(calls),1)
