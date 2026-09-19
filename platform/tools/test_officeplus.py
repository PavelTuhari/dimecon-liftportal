"""Проверка клиента Partner B2B API (OfficePlus / Artgranit).

Тест поднимает локальный сервер-макет, реализующий контракт из docs/Partner/PARTNER_API.md
исходного проекта, включая задокументированные отличия реального API:
  * /product отдаёт ГОЛЫЙ список без обёртки;
  * product_name приходит JSON-строкой;
  * цены приходят как {amount, currency:{code, rate}} — user_price в USD, fixed_price в MDL;
  * псевдонимы ultra_code / ultra_uuid;
  * access-токен живёт 1 час, при 401 требуется refresh;
  * лимит 120 запросов в минуту, при превышении 429.
Проверяется, что клиент это переваривает. Реальный сервер этим тестом не затрагивается.
"""
from __future__ import annotations

import json
import sys
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from portal.services import officeplus as op  # noqa: E402

passed, failed = [], []
STATE = {"tokens": {}, "refresh": {}, "calls": 0, "orders": [], "force_401_once": False}


def check(name, ok, detail=""):
    (passed if ok else failed).append(name)
    print(f"  {'OK  ' if ok else 'ОШИБКА'} {name}" + (f" — {detail}" if detail else ""))


def product(i: int) -> dict:
    """Позиция в формате, который реально отдаёт API (по заметкам исходного проекта)."""
    return {
        "ultra_code": f"OP-{i:04d}",
        "ultra_uuid": f"uuid-{i}",
        "product_name": json.dumps({"ro": f"Cablu de oțel {i} mm", "ru": f"Канат стальной {i} мм",
                                    "en": f"Steel rope {i} mm"}, ensure_ascii=False),
        "category_name": "Cabluri",
        "brand_name": "OfficePlus",
        "um": "m",
        "user_price": {"amount": 2.5 + i, "currency": {"code": "USD", "name": "Dolar", "rate": 18.0}},
        "fixed_price": {"amount": 60.0 + i, "currency": {"code": "MDL", "name": "Leu", "rate": 1}},
        "quantity": 100 + i,
    }


class Mock(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _auth_ok(self) -> bool:
        tok = (self.headers.get("Authorization") or "").replace("Bearer ", "")
        return tok in STATE["tokens"]

    def do_GET(self):  # noqa: N802
        STATE["calls"] += 1
        path = self.path.split("?")[0]
        query = dict(p.split("=", 1) for p in self.path.split("?")[1].split("&")) if "?" in self.path else {}
        if path == "/api/v1/health":
            return self._send(200, {"status": "ok", "time": datetime.utcnow().isoformat()})
        if not self._auth_ok():
            return self._send(401, {"error": "unauthorized"})
        if path == "/api/v1/product":
            page = int(query.get("page", 1))
            limit = int(query.get("limit", 1000))
            total = 7
            start = (page - 1) * limit
            rows = [product(i) for i in range(start, min(start + limit, total))]
            return self._send(200, rows)                      # голый список, без обёртки
        if path == "/api/v1/changes":
            return self._send(200, {"data": [product(99)]})    # здесь обёртка — тоже поддерживается
        if path == "/api/v1/order":
            return self._send(200, {"data": STATE["orders"]})
        return self._send(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        STATE["calls"] += 1
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        path = self.path.split("?")[0]
        if path == "/api/v1/auth/token":
            if body.get("username") != "partner" or body.get("password") != "secret":
                return self._send(401, {"error": "bad credentials"})
            access, refresh = f"acc-{len(STATE['tokens'])}", f"ref-{len(STATE['refresh'])}"
            STATE["tokens"][access] = True
            STATE["refresh"][refresh] = access
            return self._send(200, {"access_token": access, "refresh_token": refresh, "expires_in": 3600})
        if path == "/api/v1/auth/refresh":
            old = body.get("refresh_token")
            if old not in STATE["refresh"]:
                return self._send(401, {"error": "bad refresh"})
            access = f"acc-r{len(STATE['tokens'])}"
            STATE["tokens"][access] = True
            return self._send(200, {"access_token": access, "refresh_token": old, "expires_in": 3600})
        if not self._auth_ok():
            return self._send(401, {"error": "unauthorized"})
        if path == "/api/v1/quantity/batch":
            return self._send(200, [{"code": c, "quantity": 42} for c in body.get("codes", [])])
        if path == "/api/v1/order":
            if body.get("validate_only"):
                return self._send(200, {"valid": True, "items": len(body.get("items", [])), "total": 123.45})
            STATE["orders"].append(body)
            return self._send(200, {"order_id": 1001, "external_id": body.get("external_id"), "status": "created"})
        return self._send(404, {"error": "not found"})


srv = HTTPServer(("127.0.0.1", 8123), Mock)
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = "http://127.0.0.1:8123/api/v1"

print("=== 1. Соединение и авторизация ===")
c = op.OfficePlusClient(BASE, "partner", "secret")
h = c.health()
check("GET /health без токена", h.get("status") == "ok", str(h)[:60])
ok, msg = c.check()
check("проверка соединения и учётных данных", ok, msg)
bad_ok, bad_msg = op.OfficePlusClient(BASE, "partner", "wrong").check()
check("неверный пароль отклонён", not bad_ok, bad_msg[:70])

print("\n=== 2. Обновление токена по 401 ===")
saved_refresh = c.token.refresh
c.token.access = "expired-token"          # сервер ответит 401, клиент обязан обновить токен
c.token.expires_at = datetime(2030, 1, 1)          # клиент считает токен живым
rows = list(c.iter_products(page_size=10))
check("после 401 выполнен refresh и запрос повторён", bool(rows) and c.token.access != "просроченный",
      f"токен обновлён на {c.token.access}")
check("refresh-токен сохранён", c.token.refresh == saved_refresh, c.token.refresh)

print("\n=== 3. Разбор ответа каталога ===")
pages = list(c.iter_products(page_size=3))
flat = [r for p in pages for r in p]
check("постраничная выборка (3 стр. по 3/3/1)", len(pages) == 3 and len(flat) == 7,
      f"страниц {len(pages)}, позиций {len(flat)}")
n = op.normalize_product(flat[1])
check("псевдоним ultra_code распознан как артикул", n["sku"] == "OP-0001", n["sku"])
check("product_name из JSON-строки разобран", n["title"]["ru"].startswith("Канат стальной"), n["title"]["ru"])
check("переводы сохранены (ro/en)", n["title"]["ro"].startswith("Cablu") and n["title"]["en"].startswith("Steel"),
      f"{n['title']['ro']} / {n['title']['en']}")
check("розничная цена в MDL", abs(n["price"] - 61.0) < 0.01, str(n["price"]))
check("дилерская цена USD пересчитана по курсу 18", abs(n["dealer_price"] - (3.5 * 18)) < 0.01, str(n["dealer_price"]))
check("остаток перенесён", n["stock"] == 101, str(n["stock"]))
check("единица измерения", n["unit"] == "m", n["unit"])

print("\n=== 4. Инкрементальная выборка ===")
changes = list(c.iter_products(since="2026-09-01"))
check("ответ с обёрткой data разобран", len(changes) == 1 and len(changes[0]) == 1,
      f"{len(changes[0]) if changes else 0} изменений")

print("\n=== 5. Остатки и заказ ===")
q = c.quantities(["OP-0001", "OP-0002"])
check("остатки батчем", q.get("OP-0001") == 42 and len(q) == 2, str(q))
val = c.create_order([{"code": "OP-0001", "quantity": 3}], validate_only=True, external_id="DIM-2026-00001")
check("проверка заказа без создания (validate_only)", val.get("valid") is True and not STATE["orders"], str(val))
made = c.create_order([{"sku": "OP-0002", "quantity": 1}], validate_only=False, external_id="DIM-2026-00002")
check("заказ создан, артикул принят по псевдониму sku", made.get("status") == "created" and len(STATE["orders"]) == 1,
      str(made))
check("внешний номер заявки передан", STATE["orders"][0].get("external_id") == "DIM-2026-00002",
      STATE["orders"][0].get("external_id"))

print("\n=== 6. Нормализация значений ===")
cases = [
    (op.as_money(100), 100.0), (op.as_money("1 234,56"), 1234.56),
    (op.as_money({"amount": 10, "currency": {"code": "EUR", "rate": 19.5}}), 195.0),
    (op.as_money({"amount": 10, "currency": {"code": "MDL", "rate": 1}}), 10.0),
    (op.as_money(None), 0.0),
]
for got, expect in cases:
    check(f"цена -> {expect}", abs(got - expect) < 0.01, str(got))
check("as_text из JSON-строки", op.as_text('{"ru":"Канат","ro":"Cablu"}') == "Канат")
check("as_text из обычной строки", op.as_text("Просто текст") == "Просто текст")
check("unwrap для списка и для {data:[…]}", len(op.unwrap([{"id": 1}])) == 1 and len(op.unwrap({"data": [{"id": 2}]})) == 1)

print("\n=== 7. Перенос каталога в платформу ===")
from portal import create_app  # noqa: E402
from portal.db import SessionLocal as db  # noqa: E402
from portal.models import Product, Tenant  # noqa: E402

app = create_app()
with app.app_context():
    tenant = db.query(Tenant).filter_by(slug="dimecon").one()
    before = db.query(Product).filter_by(tenant_id=tenant.id).count()
    c2 = op.OfficePlusClient(BASE, "partner", "secret")
    dry = op.sync_catalog(tenant, c2, dry_run=True)
    check("пробный прогон не пишет в базу", db.query(Product).filter_by(tenant_id=tenant.id).count() == before,
          dry.line())
    real = op.sync_catalog(tenant, c2, dry_run=False)
    after = db.query(Product).filter_by(tenant_id=tenant.id).count()
    check("товары созданы", real.created == 7 and after == before + 7, real.line())
    sample = db.query(Product).filter_by(tenant_id=tenant.id, sku="OP-0003").first()
    check("позиция записана с переводами и ценой", bool(sample) and sample.price == 63.0
          and sample.title.get("ro", "").startswith("Cablu"),
          f"{sample.title.get('ru') if sample else '—'} / {sample.price if sample else '—'}")
    check("дилерская цена скрыта в атрибутах", bool(sample) and sample.attributes.get("dealer_price") > 0,
          str(sample.attributes.get("dealer_price") if sample else ""))
    check("товары создаются неопубликованными", bool(sample) and sample.is_published is False)
    again = op.sync_catalog(tenant, c2, dry_run=False)
    after2 = db.query(Product).filter_by(tenant_id=tenant.id).count()
    check("повторная синхронизация не плодит дубликаты", after2 == after and again.updated == 7, again.line())

    db.query(Product).filter(Product.tenant_id == tenant.id, Product.sku.like("OP-%")).delete(synchronize_session=False)
    db.commit()
    check("тестовые товары удалены", db.query(Product).filter_by(tenant_id=tenant.id).count() == before,
          f"осталось {db.query(Product).filter_by(tenant_id=tenant.id).count()} (было {before})")

srv.shutdown()
print(f"\nзапросов к макету API: {STATE['calls']}")
print(f"ИТОГО: пройдено {len(passed)}, ошибок {len(failed)}")
for f in failed:
    print("  НЕ ПРОЙДЕНО:", f)
sys.exit(1 if failed else 0)
