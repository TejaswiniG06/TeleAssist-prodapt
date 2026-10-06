"""Start the local microservices and dashboard; Ctrl+C stops only our children."""
import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import httpx
import psutil
from teleassist.common.access import AccessPolicy
from teleassist.resolution.llm import load_environment

ROOT = Path(__file__).resolve().parent


def stop_process(child):
    """Windows venv launchers can have a Python child; stop the whole owned tree."""
    try:
        processes = psutil.Process(child.pid).children(recursive=True)
    except psutil.NoSuchProcess:
        processes = []
    for process in reversed(processes):
        try:
            process.terminate()
        except psutil.NoSuchProcess:
            pass
    if child.poll() is None:
        child.terminate()
    _, alive = psutil.wait_procs(processes, timeout=10)
    for process in alive:
        try:
            process.kill()
        except psutil.NoSuchProcess:
            pass
    try:
        child.wait(timeout=10)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait(timeout=10)


def available(port):
    with socket.socket() as sock:
        try:
            sock.bind(('127.0.0.1', port))
        except OSError:
            raise RuntimeError(f'Port {port} is already in use. Stop the existing TeleAssist setup first.') from None


def wait_ready(url, children):
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        if any(child.poll() is not None for child in children):
            raise RuntimeError('A service exited during startup. Check its log in runtime/logs.')
        try:
            if httpx.get(url, timeout=2).is_success:
                return
        except httpx.HTTPError:
            pass
        time.sleep(.2)
    raise RuntimeError('Startup timed out. Check runtime/logs before retrying.')


def warm_search(url, api_key=''):
    """Load semantic search and report authentication, download and transport failures."""
    retry_hint = 'Retry, or run: python start.py --skip-warmup. Check runtime/logs for details.'
    headers = {'X-API-Key': api_key} if api_key else {}
    try:
        with httpx.Client(timeout=180) as client:
            response = client.post(
                url + '/search', headers=headers,
                json={'query': 'slow broadband speed', 'mode': 'hybrid'},
            )
            if response.status_code in (401, 403):
                raise RuntimeError(
                    'Search warmup access was denied. Check the retrieval application key '
                    '(RETRIEVAL_API_KEY or TELEASSIST_AGENT_KEY) and AUTH_MODE.'
                )
            if response.status_code == 503:
                raise RuntimeError('Semantic search could not load its model/cache. ' + retry_hint)
            if not response.is_success:
                raise RuntimeError(
                    f'Search warmup returned HTTP {response.status_code}. Check runtime/logs.'
                )
            if not client.get(url + '/ready?require_semantic=true').is_success:
                raise RuntimeError('Semantic search is not ready. ' + retry_hint)
    except httpx.TimeoutException:
        raise RuntimeError(
            'Semantic search warmup timed out; the first model download may still be pending. '
            + retry_hint
        ) from None
    except httpx.RequestError:
        raise RuntimeError(
            'Could not reach retrieval during search warmup. Check the service and runtime/logs.'
        ) from None


def run(args):
    load_environment(ROOT / '.env')
    AccessPolicy.from_environment()  # Fail before starting any children on invalid authentication.
    ports = [args.dashboard_port, args.retrieval_port, args.resolution_port] if args.mode == 'split' else [args.dashboard_port, args.combined_port]
    if len(set(ports)) != len(ports):
        raise RuntimeError('Each process needs a different port.')
    for port in ports:
        available(port)
    # Standard ports detect the common accidental second writer; custom deployments must
    # still give each retrieval writer a separate TELEASSIST_STATE_DIR.
    available(args.combined_port if args.mode == 'split' else args.retrieval_port)
    env = dict(os.environ)
    retrieval_url = f'http://127.0.0.1:{args.retrieval_port}'
    api_url = f'http://127.0.0.1:{args.resolution_port if args.mode == "split" else args.combined_port}'
    env['RETRIEVAL_URL'] = retrieval_url
    env['RETRIEVAL_API_KEY'] = env.get('RETRIEVAL_API_KEY') or env.get('TELEASSIST_AGENT_KEY', '')
    env['TELEASSIST_API_URL'] = api_url
    env['TELEASSIST_EDITOR_URL'] = retrieval_url if args.mode == 'split' else api_url
    log_root = Path(env.get('TELEASSIST_STATE_DIR', str(ROOT / 'runtime'))) / 'logs'
    log_root.mkdir(parents=True, exist_ok=True)
    children, logs = [], []

    def start(name, arguments):
        log = (log_root / f'{name}.log').open('w', encoding='utf-8')
        logs.append(log)
        children.append(subprocess.Popen([sys.executable, '-m', *arguments], cwd=ROOT,
            env=env, stdout=log, stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0))

    try:
        module = 'retrieval_api' if args.mode == 'split' else 'api'
        port = args.retrieval_port if args.mode == 'split' else args.combined_port
        start(module, ['uvicorn', module + ':app', '--host', '127.0.0.1', '--port', str(port)])
        evidence_url = retrieval_url if args.mode == 'split' else api_url
        wait_ready(evidence_url + '/live', children)
        if not args.skip_warmup:
            print('Loading local semantic search (no LLM call)...', flush=True)
            warm_search(evidence_url, env['RETRIEVAL_API_KEY'])
        if args.mode == 'split':
            start('resolution_api', ['uvicorn', 'resolution_api:app', '--host', '127.0.0.1', '--port', str(args.resolution_port)])
            wait_ready(api_url + '/ready', children)
        # Provider credentials stay in backend processes, never the dashboard process.
        for name in ('GEMINI_API_KEY', 'GROQ_API_KEY', 'RETRIEVAL_API_KEY'):
            env.pop(name, None)
        start('dashboard', ['streamlit', 'run', 'dashboard.py', '--server.headless', 'true',
                            '--server.address', '127.0.0.1', '--server.port', str(args.dashboard_port)])
        wait_ready(f'http://127.0.0.1:{args.dashboard_port}/_stcore/health', children)
        print(f'{args.mode.capitalize()} mode ready: http://127.0.0.1:{args.dashboard_port}', flush=True)
        print('Press Ctrl+C to stop these processes. Saved data stays on disk.', flush=True)
        while all(child.poll() is None for child in children):
            time.sleep(.5)
        raise RuntimeError('A process stopped. Check service logs before restarting.')
    finally:
        for child in children:
            stop_process(child)
        for log in logs:
            log.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['split', 'combined'], default='split')
    parser.add_argument('--retrieval-port', type=int, default=8001)
    parser.add_argument('--resolution-port', type=int, default=8002)
    parser.add_argument('--combined-port', type=int, default=8000)
    parser.add_argument('--dashboard-port', type=int, default=8501)
    parser.add_argument('--skip-warmup', action='store_true', help='Allow keyword-only startup; first semantic query loads the model.')
    args = parser.parse_args()
    try:
        run(args)
    except KeyboardInterrupt:
        print('\nStopped.')
    except (RuntimeError, ValueError, httpx.HTTPError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
