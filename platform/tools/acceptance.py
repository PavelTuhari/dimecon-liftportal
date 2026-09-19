"""Приёмочные измерения для акта тестирования: БД, целостность, кодировка, производительность, API."""
from __future__ import annotations

import json
import statistics
import sys
import time
import urllib.request

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import text  # noqa: E402

from portal import create_app  # noqa: E402
from portal import db as _db  # noqa: E402
from portal.db import SessionLocal  # noqa: E402
from portal.models import Equipment, Order, Tenant  # noqa: E402

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8090"
app = create_app()

print("=" * 78)
print("1. СУБД")
print("=" * 78)
with _db.engine.connect() as c:
    ver = c.execute(text("SELECT VERSION()")).scalar()
    charset = c.execute(text("SELECT @@character_set_database, @@collation_database")).one()
    port = c.execute(text("SELECT @@port")).scalar()
    print(f"драйвер приложения : {_db.engine.dialect.name} / {_db.engine.driver}")
    print(f"сервер             : MySQL {ver}, порт {port}")
    print(f"кодировка БД       : {charset[0]} / {charset[1]}")
    rows = c.execute(text("""SELECT table_name, engine, table_rows FROM information_schema.tables
                             WHERE table_schema='liftportal' ORDER BY table_name""")).all()
    print(f"таблиц в схеме     : {len(rows)}, движок: {set(r[1] for r in rows)}")
    idx = c.execute(text("""SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema='liftportal'""")).scalar()
    fk = c.execute(text("""SELECT COUNT(*) FROM information_schema.referential_constraints WHERE constraint_schema='liftportal'""")).scalar()
    print(f"индексов / внешних ключей : {idx} / {fk}")

print("\n" + "=" * 78)
print("2. ДАННЫЕ")
print("=" * 78)
db = SessionLocal()
counts = {}
for t in ["tenants", "users", "memberships", "equipment", "load_charts", "bookings", "services", "products",
          "cases", "pages", "contacts", "orders", "activities", "documents", "partners", "projects", "shifts",
          "reviews", "media", "outbox", "audit_log"]:
    counts[t] = db.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
    print(f"  {t:<14} {counts[t]}")

print("\n" + "=" * 78)
print("3. ЦЕЛОСТНОСТЬ МУЛЬТИАРЕНДНОСТИ")
print("=" * 78)
orphan = db.execute(text("""SELECT COUNT(*) FROM orders o LEFT JOIN tenants t ON t.id=o.tenant_id WHERE t.id IS NULL""")).scalar()
cross = db.execute(text("""SELECT COUNT(*) FROM orders o JOIN equipment e ON e.id=o.equipment_id
                           WHERE e.tenant_id <> o.tenant_id""")).scalar()
cross2 = db.execute(text("""SELECT COUNT(*) FROM orders o JOIN contacts c ON c.id=o.contact_id
                            WHERE c.tenant_id <> o.tenant_id""")).scalar()
print(f"заказов без компании                : {orphan} (норма 0)")
print(f"заказов с техникой чужой компании   : {cross} (норма 0)")
print(f"заказов с контактом чужой компании  : {cross2} (норма 0)")
for tnt in db.query(Tenant).all():
    eq = db.query(Equipment).filter_by(tenant_id=tnt.id).count()
    lc = db.execute(text("SELECT COUNT(*) FROM load_charts lc JOIN equipment e ON e.id=lc.equipment_id WHERE e.tenant_id=:t"),
                    {"t": tnt.id}).scalar()
    od = db.query(Order).filter_by(tenant_id=tnt.id).count()
    print(f"  {tnt.slug:<14} техники {eq:>3}, строк грузовых таблиц {lc:>4}, заявок {od:>3}")

print("\n" + "=" * 78)
print("4. КОДИРОВКА utf8mb4: кириллица, румынская диакритика, эмодзи")
print("=" * 78)
probe = "Проверка ăâîșț «Дименкон» 🏗 100 т"
db.execute(text("UPDATE tenants SET tagline=JSON_SET(tagline,'$.test',:v) WHERE slug='dimecon'"), {"v": probe})
db.commit()
back = db.execute(text("SELECT JSON_UNQUOTE(JSON_EXTRACT(tagline,'$.test')) FROM tenants WHERE slug='dimecon'")).scalar()
print(f"записано : {probe}")
print(f"прочитано: {back}")
print(f"совпадение: {'ДА' if back == probe else 'НЕТ'}")
db.execute(text("UPDATE tenants SET tagline=JSON_REMOVE(tagline,'$.test') WHERE slug='dimecon'"))
db.commit()

print("\n" + "=" * 78)
print("5. ПРОИЗВОДИТЕЛЬНОСТЬ (10 замеров на страницу, сервер MySQL)")
print("=" * 78)
eq_slug = db.query(Equipment.slug).filter_by(tenant_id=1, is_published=True).order_by(Equipment.sort).first()[0]
pages = [("Маркетплейс", "/"), ("Сайт компании (главная)", "/s/dimecon/"),
         ("Каталог техники", "/s/dimecon/equipment"),
         ("Карточка техники + график", f"/s/dimecon/equipment/{eq_slug}"),
         ("Визард, шаг 1", "/s/dimecon/calculator"), ("API: каталог", "/api/v1/equipment"),
         ("Выгрузка прайса XLSX", "/s/dimecon/export/pricelist.xlsx")]
perf = []
for name, path in pages:
    times = []
    for _ in range(10):
        req = urllib.request.Request(BASE + path, headers={"X-API-Key": "demo-dimecon-key"})
        t0 = time.perf_counter()
        with urllib.request.urlopen(req, timeout=30) as r:
            r.read()
            code = r.status
        times.append((time.perf_counter() - t0) * 1000)
    med, mx = statistics.median(times), max(times)
    perf.append((name, path, code, med, mx))
    print(f"  {name:<28} HTTP {code}  медиана {med:6.0f} мс  макс {mx:6.0f} мс")

print("\n" + "=" * 78)
print("6. API")
print("=" * 78)
req = urllib.request.Request(f"{BASE}/api/v1/quotes", method="POST",
                             data=json.dumps({"equipment_id": db.query(Equipment.id).filter_by(tenant_id=1).order_by(Equipment.id).first()[0], "start": "2026-10-01T09:00", "hours": 4,
                                              "distance_km": 12, "conditions": ["rigger"]}).encode(),
                             headers={"X-API-Key": "demo-dimecon-key", "Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=30) as r:
    q = json.loads(r.read())
print(f"POST /api/v1/quotes -> HTTP {r.status}, итого {q['total']} {q['currency']}, строк расчёта {len(q['lines'])}")
for line in q["lines"]:
    print(f"    {line['title']:<52} {line['amount']:>8}")
try:
    urllib.request.urlopen(urllib.request.Request(f"{BASE}/api/v1/orders"), timeout=10)
    print("БЕЗ КЛЮЧА: доступ открыт — ДЕФЕКТ")
except urllib.error.HTTPError as e:
    print(f"GET /api/v1/orders без ключа -> HTTP {e.code} (ожидается 401)")

print("\n" + "=" * 78)
print("7. ПОЧТА")
print("=" * 78)
out = db.execute(text("SELECT status, transport, COUNT(*) FROM outbox GROUP BY status, transport")).all()
for s, tr, n in out:
    print(f"  статус {s:<8} транспорт {tr or '—':<18} {n}")
print("  (SMTP компаний не настроен в тестовом контуре — письма фиксируются в журнале, не теряются)")

db.close()
print("\nГОТОВО")
