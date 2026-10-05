"""Reproduce the audited optional public corpus with a pinned, checked download."""
from teleassist.common.paths import PROJECT_ROOT
import hashlib
from pathlib import Path
import httpx
from scripts.data.prepare_tickets import prepare

ROOT = PROJECT_ROOT
REVISION = 'ddf1c81a5475992c4fa6752bf1e8b4e31f07bbeb'
FILENAME = 'aa_dataset-tickets-multi-lang-5-2-50-version.csv'
URL = f'https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets/resolve/{REVISION}/{FILENAME}'
SHA256 = 'f187c090e59581c2bbf3aa1377c8db4dd647464ecf2ae51bf8966e42e0ed6bc0'


def checked_download(destination, url=URL, expected_hash=SHA256, transport=None):
    destination = Path(destination)
    if destination.exists() and hashlib.sha256(destination.read_bytes()).hexdigest() == expected_hash:
        return 'existing_verified_file'
    destination.parent.mkdir(parents=True,exist_ok=True)
    temporary = destination.with_suffix('.download')
    try:
        digest, size = hashlib.sha256(), 0
        with httpx.Client(timeout=60,follow_redirects=True,transport=transport) as client:
            with client.stream('GET',url) as response:
                response.raise_for_status()
                with temporary.open('wb') as output:
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > 40*1024*1024:
                            raise ValueError('Public file exceeds audited size bound.')
                        digest.update(chunk)
                        output.write(chunk)
        if digest.hexdigest() != expected_hash:
            raise ValueError('Public file checksum differs; existing data preserved.')
        temporary.replace(destination)
        return 'downloaded_and_verified'
    finally:
        if temporary.exists():
            temporary.unlink()


def main():
    source = ROOT/'scratch/tobi-tickets.csv'
    result = checked_download(source)
    prepare(source,ROOT/'scratch/prepared')
    print(f'Public data {result}; pinned revision {REVISION}; educational CC-BY-NC-4.0 use with Tobi-Bueck / Softoft attribution.')


if __name__ == '__main__':
    main()
