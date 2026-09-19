"""Диагностика задержки: localhost vs 127.0.0.1, соединение vs рендер."""
import socket
import statistics
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PATH = "/s/dimecon/"


def bench(base, n=8):
    ts = []
    for _ in range(n):
        t0 = time.perf_counter()
        urllib.request.urlopen(base + PATH, timeout=30).read()
        ts.append((time.perf_counter() - t0) * 1000)
    return statistics.median(ts), min(ts), max(ts)


print("резолв localhost:", socket.getaddrinfo("localhost", 8090, proto=socket.IPPROTO_TCP)[:3])
for base in ("http://127.0.0.1:8090", "http://localhost:8090"):
    med, lo, hi = bench(base)
    print(f"{base:26} медиана {med:8.1f} мс   мин {lo:7.1f}   макс {hi:7.1f}")

# чистое время соединения
for host in ("127.0.0.1", "localhost"):
    ts = []
    for _ in range(5):
        t0 = time.perf_counter()
        s = socket.create_connection((host, 8090), timeout=10)
        ts.append((time.perf_counter() - t0) * 1000)
        s.close()
    print(f"TCP-соединение к {host:<10} медиана {statistics.median(ts):7.1f} мс")

# серверный рендер без сети (test_client)
sys.path.insert(0, ".")
from portal import create_app  # noqa: E402

app = create_app()
c = app.test_client()
for name, url in [("главная сайта", "/s/dimecon/"), ("каталог", "/s/dimecon/equipment"),
                  ("карточка техники", "/s/dimecon/equipment/grove-gmk-5100"), ("маркетплейс", "/")]:
    ts = []
    for _ in range(12):
        t0 = time.perf_counter()
        r = c.get(url)
        ts.append((time.perf_counter() - t0) * 1000)
    print(f"рендер БЕЗ сети · {name:<18} медиана {statistics.median(ts):7.1f} мс  (HTTP {r.status_code})")
