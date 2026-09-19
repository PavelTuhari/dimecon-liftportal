"""Клиент Partner B2B API системы OfficePlus (модуль `partner` платформы Artgranit).

Контракт по docs/Partner/PARTNER_API.md исходного проекта:
  base URL      https://officeplus.md/api/v1  (реальные маршруты /UNA.md/orasldev/partner/api/...)
  авторизация   POST /auth/token | /auth/refresh | /auth/revoke, access 1 ч, refresh 30 дней
  чтение        GET /product (+/{id}, POST /batch), /category, /brand, /quantity, /changes?since&entity
  запись        POST /order (validate_only:true — проверка без создания), GET /order
  служебное     GET /health, лимит 120 запросов в минуту на партнёра

Учтены отличия реального API от документации, зафиксированные в исходном проекте:
  * ответ /product — список без обёртки либо объект с ключом data/items;
  * product_name приходит как JSON-строка '{"ro":…}', а не как объект;
  * цена приходит как {amount, currency:{code,rate}} — нормализуется в MDL (amount × rate);
  * псевдонимы полей ultra_code/ultra_uuid принимаются наравне с code/uuid.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Iterable

DEFAULT_BASE = "https://officeplus.md/api/v1"
RATE_LIMIT_PER_MIN = 120
USER_AGENT = "LiftPortal/1.0 (+partner-api-client)"


class OfficePlusError(RuntimeError):
    pass


@dataclass
class Token:
    access: str = ""
    refresh: str = ""
    expires_at: datetime | None = None

    @property
    def valid(self) -> bool:
        return bool(self.access) and bool(self.expires_at) and datetime.utcnow() < self.expires_at - timedelta(seconds=60)


@dataclass
class SyncReport:
    fetched: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    pages: int = 0
    errors: list[str] = field(default_factory=list)
    samples: list[dict] = field(default_factory=list)
    dry_run: bool = True

    def line(self) -> str:
        mode = "пробная синхронизация" if self.dry_run else "синхронизация"
        return (f"{mode}: получено {self.fetched} позиций за {self.pages} стр., "
                f"создано {self.created}, обновлено {self.updated}, пропущено {self.skipped}")


# --------------------------------------------------------------------- нормализация

def pick(row: dict, *names, default=None):
    """Значение по первому существующему имени: поддержка псевдонимов ultra_* и code/uuid."""
    for n in names:
        if n in row and row[n] not in (None, ""):
            return row[n]
    return default


def as_text(value: Any, lang: str = "ru") -> str:
    """product_name приходит объектом, JSON-строкой или простой строкой."""
    if value in (None, ""):
        return ""
    if isinstance(value, dict):
        return str(value.get(lang) or value.get("ro") or value.get("ru") or value.get("en") or next(iter(value.values()), ""))
    text = str(value).strip()
    if text.startswith("{") and text.endswith("}"):
        try:
            return as_text(json.loads(text), lang)
        except (ValueError, TypeError):
            return text
    return text


def as_i18n(value: Any) -> dict:
    if isinstance(value, dict):
        base = {k.lower(): str(v) for k, v in value.items() if isinstance(v, (str, int, float))}
    else:
        text = str(value or "").strip()
        if text.startswith("{"):
            try:
                return as_i18n(json.loads(text))
            except (ValueError, TypeError):
                base = {}
            else:
                base = {}
        else:
            base = {}
        if not base:
            base = {"ru": text, "ro": text, "en": text}
    out = {}
    for lang in ("ru", "ro", "en"):
        out[lang] = base.get(lang) or base.get("ro") or base.get("ru") or base.get("en") or ""
    return out


def as_money(value: Any) -> float:
    """Цена: число либо {amount, currency:{code, rate}} — приводим к MDL."""
    if value in (None, ""):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        amount = value.get("amount", value.get("value", 0))
        try:
            amount = float(str(amount).replace(",", "."))
        except (TypeError, ValueError):
            return 0.0
        cur = value.get("currency") or {}
        if isinstance(cur, dict):
            code = str(cur.get("code", "MDL")).upper()
            rate = cur.get("rate", 1)
            try:
                rate = float(rate)
            except (TypeError, ValueError):
                rate = 1.0
            if code != "MDL" and rate:
                amount *= rate
        return round(amount, 2)
    try:
        return float(str(value).replace(" ", "").replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def unwrap(payload: Any) -> list[dict]:
    """Ответ приходит списком либо объектом с data/items/results."""
    if payload is None:
        return []
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in ("data", "items", "results", "products", "rows"):
            if isinstance(payload.get(key), list):
                return [x for x in payload[key] if isinstance(x, dict)]
        if any(k in payload for k in ("id", "code", "ultra_code")):
            return [payload]
    return []


# --------------------------------------------------------------------- клиент

class OfficePlusClient:
    def __init__(self, base_url: str = DEFAULT_BASE, username: str = "", password: str = "",
                 token: Token | None = None, timeout: int = 30, opener=None):
        self.base = (base_url or DEFAULT_BASE).rstrip("/")
        self.username = username
        self.password = password
        self.token = token or Token()
        self.timeout = timeout
        self._opener = opener or urllib.request.build_opener()
        self._calls: list[float] = []

    # ---- транспорт ----
    def _throttle(self):
        now = time.monotonic()
        self._calls = [t for t in self._calls if now - t < 60]
        if len(self._calls) >= RATE_LIMIT_PER_MIN:
            time.sleep(max(0.0, 60 - (now - self._calls[0])))
            self._calls = []
        self._calls.append(time.monotonic())

    def _request(self, method: str, path: str, *, params: dict | None = None, body: Any = None,
                 auth: bool = True, retry_auth: bool = True) -> Any:
        self._throttle()
        url = self.base + path
        if params:
            url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "")})
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
        if data:
            headers["Content-Type"] = "application/json"
        if auth:
            if not self.token.valid:
                self.authenticate()
            headers["Authorization"] = f"Bearer {self.token.access}"
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
        except (UnicodeEncodeError, ValueError) as exc:
            raise OfficePlusError(f"некорректные заголовки запроса (проверьте токен и адрес): {exc}") from exc
        try:
            with self._opener.open(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8", "replace")
            return json.loads(raw) if raw.strip() else {}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:400]
            if exc.code == 401 and auth and retry_auth:
                # гасим только access: refresh живёт 30 дней и должен быть использован,
                # полный вход по паролю — лишь запасной путь внутри authenticate()
                self.token.access = ""
                self.token.expires_at = None
                self.authenticate()
                return self._request(method, path, params=params, body=body, auth=auth, retry_auth=False)
            if exc.code == 429:
                time.sleep(5)
                return self._request(method, path, params=params, body=body, auth=auth, retry_auth=False)
            raise OfficePlusError(f"HTTP {exc.code} на {method} {path}: {detail}") from exc
        except UnicodeEncodeError as exc:
            raise OfficePlusError(f"токен доступа содержит недопустимые символы: {exc}") from exc
        except urllib.error.URLError as exc:
            raise OfficePlusError(f"нет связи с {self.base}: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise OfficePlusError(f"ответ не в формате JSON на {method} {path}") from exc

    # ---- авторизация ----
    def authenticate(self) -> Token:
        if self.token.refresh:
            try:
                data = self._request("POST", "/auth/refresh", body={"refresh_token": self.token.refresh},
                                     auth=False)
                return self._store_token(data)
            except OfficePlusError:
                self.token = Token()
        if not (self.username and self.password):
            raise OfficePlusError("не заданы логин и пароль партнёра")
        data = self._request("POST", "/auth/token",
                             body={"username": self.username, "password": self.password}, auth=False)
        return self._store_token(data)

    def _store_token(self, data: dict) -> Token:
        payload = data.get("data") if isinstance(data.get("data"), dict) else data
        access = pick(payload, "access_token", "access", "token")
        if not access:
            raise OfficePlusError(f"ответ авторизации без токена: {str(payload)[:200]}")
        ttl = int(pick(payload, "expires_in", "expires", default=3600) or 3600)
        self.token = Token(access=access, refresh=pick(payload, "refresh_token", "refresh", default="") or "",
                           expires_at=datetime.utcnow() + timedelta(seconds=ttl))
        return self.token

    def revoke(self):
        if self.token.access:
            try:
                self._request("POST", "/auth/revoke", body={"refresh_token": self.token.refresh}, retry_auth=False)
            except OfficePlusError:
                pass
        self.token = Token()

    # ---- чтение ----
    def health(self) -> dict:
        return self._request("GET", "/health", auth=False)

    def check(self) -> tuple[bool, str]:
        """Проверка соединения и учётных данных — для кнопки в кабинете."""
        try:
            h = self.health()
            status = pick(h, "status", "state", default="ok") if isinstance(h, dict) else "ok"
        except OfficePlusError as exc:
            return False, f"сервис недоступен: {exc}"
        try:
            self.authenticate()
        except OfficePlusError as exc:
            return False, f"сервис отвечает ({status}), но авторизация не прошла: {exc}"
        return True, f"соединение установлено, сервис {status}, токен действует до {self.token.expires_at:%H:%M:%S}"

    def iter_products(self, *, page_size: int = 1000, max_pages: int = 100,
                      since: str | None = None) -> Iterable[list[dict]]:
        """Полный каталог постранично либо изменения с отметки времени."""
        if since:
            data = self._request("GET", "/changes", params={"since": since, "entity": "product"})
            rows = unwrap(data)
            if rows:
                yield rows
            return
        page = 1
        while page <= max_pages:
            data = self._request("GET", "/product", params={"page": page, "limit": page_size,
                                                            "sort": "updated_at"})
            rows = unwrap(data)
            if not rows:
                return
            yield rows
            if len(rows) < page_size:
                return
            page += 1

    def quantities(self, codes: list[str]) -> dict[str, float]:
        if not codes:
            return {}
        data = self._request("POST", "/quantity/batch", body={"codes": codes})
        out = {}
        for row in unwrap(data):
            code = str(pick(row, "code", "ultra_code", "id", default=""))
            if code:
                out[code] = as_money(pick(row, "quantity", "qty", "stock", default=0))
        return out

    # ---- запись ----
    def create_order(self, items: list[dict], *, comment: str = "", validate_only: bool = True,
                     external_id: str = "") -> dict:
        body = {
            "validate_only": bool(validate_only),
            "comment": comment,
            "external_id": external_id,
            "items": [{"code": str(pick(i, "code", "sku", "ultra_code", default="")),
                       "quantity": float(i.get("quantity", 1))} for i in items if pick(i, "code", "sku", "ultra_code")],
        }
        if not body["items"]:
            raise OfficePlusError("нет позиций для заказа")
        return self._request("POST", "/order", body=body)

    def orders(self, since: str | None = None) -> list[dict]:
        return unwrap(self._request("GET", "/order", params={"since": since} if since else None))


# --------------------------------------------------------------------- перенос каталога

def normalize_product(row: dict) -> dict:
    """Позиция каталога OfficePlus -> поля товара платформы."""
    code = str(pick(row, "code", "ultra_code", "sku", "id", default="")).strip()
    name = pick(row, "product_name", "name", "denumire", "title", default="")
    price = pick(row, "fixed_price", "retail_price", "price", "user_price", default=0)
    return {
        "sku": code,
        "title": as_i18n(name),
        "category": as_text(pick(row, "category_name", "category", "group", default=""), "ru"),
        "brand": as_text(pick(row, "brand_name", "brand", default=""), "ru"),
        "price": as_money(price),
        "dealer_price": as_money(pick(row, "user_price", "dealer_price", default=0)),
        "unit": as_text(pick(row, "um", "unit", "measure", default="шт"), "ru") or "шт",
        "stock": as_money(pick(row, "quantity", "qty", "stock", default=0)),
        "uuid": str(pick(row, "uuid", "ultra_uuid", default="")),
        "image": str(pick(row, "image", "image_url", "photo", default="")),
    }


def sync_catalog(tenant, client: OfficePlusClient, *, dry_run: bool = True, limit_pages: int = 20,
                 since: str | None = None, category_prefix: str = "OfficePlus") -> SyncReport:
    """Перенос каталога партнёра в раздел «В продаже» платформы.

    Сопоставление по артикулу (sku). Цены берутся розничные; дилерская цена
    сохраняется в атрибутах позиции, чтобы не показывать её клиентам.
    """
    from ..db import SessionLocal as db
    from ..models import Product

    rep = SyncReport(dry_run=dry_run)
    existing = {p.sku: p for p in db.query(Product).filter_by(tenant_id=tenant.id).all() if p.sku}

    for page_rows in client.iter_products(since=since, max_pages=limit_pages):
        rep.pages += 1
        for row in page_rows:
            try:
                p = normalize_product(row)
                if not p["sku"] or not any(p["title"].values()):
                    rep.skipped += 1
                    continue
                rep.fetched += 1
                if len(rep.samples) < 8:
                    rep.samples.append({"sku": p["sku"], "title": p["title"]["ru"], "price": p["price"],
                                        "stock": p["stock"], "category": p["category"]})
                if dry_run:
                    (rep.updated if p["sku"] in existing else rep.created)
                    if p["sku"] in existing:
                        rep.updated += 1
                    else:
                        rep.created += 1
                    continue
                attrs = {"source": "officeplus", "uuid": p["uuid"], "brand": p["brand"],
                         "dealer_price": p["dealer_price"], "synced_at": datetime.utcnow().isoformat(timespec="seconds")}
                found = existing.get(p["sku"])
                if found:
                    found.title = p["title"] or found.title
                    found.price = p["price"] or found.price
                    found.stock = p["stock"]
                    found.unit = p["unit"] or found.unit
                    found.attributes = {**(found.attributes or {}), **attrs}
                    if p["image"] and not found.image_url:
                        found.image_url = p["image"]
                    rep.updated += 1
                else:
                    db.add(Product(tenant_id=tenant.id, sku=p["sku"],
                                   slug=f"op-{p['sku'].lower()}"[:110],
                                   category=p["category"] or category_prefix, title=p["title"],
                                   unit=p["unit"], price=p["price"], stock=p["stock"],
                                   is_published=False, image_url=p["image"], attributes=attrs))
                    rep.created += 1
            except Exception as exc:  # noqa: BLE001
                rep.errors.append(f"позиция {pick(row, 'code', 'id', default='?')}: {exc}")
                rep.skipped += 1
    if not dry_run:
        db.commit()
    return rep


def push_order(tenant, client: OfficePlusClient, order, *, validate_only: bool = True) -> dict:
    """Отправка заказа товаров платформы в ERP партнёра."""
    from ..db import SessionLocal as db
    from ..models import Product

    items = []
    for line in (order.breakdown or []):
        sku = line.get("code") or line.get("sku")
        if sku:
            items.append({"code": sku, "quantity": line.get("qty", 1)})
    if not items and order.cargo:
        p = db.query(Product).filter_by(tenant_id=tenant.id, sku=order.cargo).first()
        if p:
            items.append({"code": p.sku, "quantity": 1})
    if not items:
        raise OfficePlusError("в заявке нет товарных позиций с артикулом")
    return client.create_order(items, comment=f"Заявка {order.number} из LiftPortal",
                               external_id=order.number, validate_only=validate_only)


def client_from_tenant(tenant) -> OfficePlusClient:
    cfg = (tenant.settings or {}).get("officeplus") or {}
    tok = Token(access=cfg.get("access_token", ""), refresh=cfg.get("refresh_token", ""),
                expires_at=datetime.fromisoformat(cfg["expires_at"]) if cfg.get("expires_at") else None)
    return OfficePlusClient(cfg.get("base_url") or DEFAULT_BASE, cfg.get("username", ""),
                            cfg.get("password", ""), token=tok)


def save_token(tenant, client: OfficePlusClient):
    from ..db import SessionLocal as db

    settings = dict(tenant.settings or {})
    cfg = dict(settings.get("officeplus") or {})
    cfg.update({"access_token": client.token.access, "refresh_token": client.token.refresh,
                "expires_at": client.token.expires_at.isoformat() if client.token.expires_at else ""})
    settings["officeplus"] = cfg
    tenant.settings = settings
    db.commit()
