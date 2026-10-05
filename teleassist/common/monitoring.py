"""Bounded in-process counters and latency samples; no complaint logging."""
from collections import Counter, defaultdict, deque
import math
from threading import Lock
import time
import psutil


def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered)*fraction)-1)] if ordered else None


class Metrics:
    def __init__(self):
        self.started = time.monotonic()
        self.lock = Lock()
        self.counts, self.errors, self.fallbacks, self.resolutions = Counter(), Counter(), Counter(), Counter()
        self.latencies = defaultdict(lambda:deque(maxlen=256))
        self.inflight = 0
        self.process = psutil.Process()

    def begin(self):
        with self.lock:
            self.inflight += 1

    def finish(self, route, status, seconds):
        with self.lock:
            self.inflight -= 1
            self.counts[route] += 1
            if status >= 400:
                self.errors[f'{route}:{status}'] += 1
            self.latencies[route].append(round(seconds*1000,3))

    def resolution(self, result):
        with self.lock:
            self.resolutions[result['status']] += 1
            if result.get('generation') == 'fallback':
                self.fallbacks[result['reason']] += 1

    def snapshot(self):
        with self.lock:
            data = {'uptime_seconds':round(time.monotonic()-self.started,2),
                    'requests':dict(self.counts),'http_errors':dict(self.errors),
                    'inflight':self.inflight,'resolution_outcomes':dict(self.resolutions),
                    'fallback_reasons':dict(self.fallbacks),
                    'latency_ms':{route:{'sample_count':len(values),'p50':percentile(values,.5),
                                         'p95':percentile(values,.95),'max':max(values)}
                                  for route,values in self.latencies.items()}}
        try:
            cpu = self.process.cpu_times()
            data['process'] = {'rss_bytes':self.process.memory_info().rss,
                               'cpu_seconds':round(cpu.user+cpu.system,3),
                               'threads':self.process.num_threads()}
        except psutil.Error:
            data['process'] = {'state':'unavailable'}
        data['notice'] = 'Per-process since startup; latency retains latest 256 samples per route. No raw complaint text recorded.'
        return data


def install_monitoring(app, metrics):
    @app.middleware('http')
    async def observe(request, call_next):
        started, status = time.perf_counter(), 500
        metrics.begin()
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            route = request.scope.get('route')
            metrics.finish(route.path if route else '/unmatched', status, time.perf_counter()-started)
