"""Собственный домен компании: подсказка по DNS и проверка привязки.

Проверка делает две вещи: смотрит, куда указывает имя в DNS, и стучится по этому имени
в сам сайт. Домен считается рабочим, когда сайт по нему отвечает страницей компании.
"""
from __future__ import annotations

import re
import socket
import urllib.error
import urllib.request
from datetime import datetime

from ..db import SessionLocal as db
from ..models import Domain, Tenant

HOST_RE = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))+$")


def normalize(host: str) -> str:
    host = (host or "").strip().lower()
    host = re.sub(r"^https?://", "", host).split("/")[0].split(":")[0]
    return host.rstrip(".")


def validate(host: str) -> str:
    """Пустая строка — имя годится; иначе текст ошибки."""
    if not host:
        return "укажите домен"
    if not HOST_RE.match(host):
        return "похоже на опечатку: домен пишется как example.md или crane.example.md"
    if host.endswith(".local"):
        return "локальные имена не работают в интернете"
    return ""


def dns_lookup(host: str) -> tuple[list[str], str]:
    try:
        infos = socket.getaddrinfo(host, None)
        ips = sorted({i[4][0] for i in infos})
        return ips, ""
    except socket.gaierror as exc:
        return [], f"DNS не отвечает: {exc.strerror or exc}"


def platform_ips(platform_host: str) -> list[str]:
    ips, _ = dns_lookup(normalize(platform_host))
    return ips


def instructions(tenant: Tenant, host: str, platform_host: str) -> list[dict]:
    """Что именно вписать в панели регистратора."""
    target = normalize(platform_host)
    ips = platform_ips(platform_host)
    apex = host.count(".") == 1
    rows = []
    if apex:
        for ip in ips or ["адрес сервера платформы"]:
            rows.append({"type": "A", "name": "@", "value": ip,
                         "note": "корень домена указывает на сервер платформы"})
        rows.append({"type": "CNAME", "name": "www", "value": target,
                     "note": "чтобы www.домен тоже открывался"})
    else:
        rows.append({"type": "CNAME", "name": host.split(".")[0], "value": target,
                     "note": "поддомен указывает на платформу"})
    return rows


def check(tenant: Tenant, domain: Domain, platform_host: str, timeout: int = 8) -> Domain:
    """Проверить домен: DNS и ответ сайта. Результат сохраняется в карточке домена."""
    host = normalize(domain.host)
    ips, dns_error = dns_lookup(host)
    domain.dns_target = ", ".join(ips)[:200]
    domain.http_status = None
    domain.checked_at = datetime.utcnow()

    if dns_error:
        domain.verified = False
        domain.check_note = dns_error[:255]
        db.commit()
        return domain

    expected = set(platform_ips(platform_host))
    same_server = bool(expected and set(ips) & expected)
    try:
        req = urllib.request.Request(f"http://{host}/", headers={"User-Agent": "liftportal-domain-check"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read(4096).decode("utf-8", "replace")
            domain.http_status = r.status
    except urllib.error.HTTPError as exc:
        domain.http_status = exc.code
        body = ""
    except Exception as exc:  # noqa: BLE001 — сеть заказчика бывает недоступна
        domain.verified = False
        domain.check_note = f"сайт по имени не отвечает: {str(exc)[:160]}"
        db.commit()
        return domain

    ours = tenant.name.lower() in body.lower() or f"/s/{tenant.slug}" in body
    if domain.http_status and domain.http_status < 400 and (ours or same_server):
        domain.verified = True
        domain.check_note = ("сайт компании отвечает по этому имени"
                             if ours else "имя ведёт на сервер платформы")
    else:
        domain.verified = False
        domain.check_note = (f"имя отвечает (HTTP {domain.http_status}), но это не сайт компании — "
                             "проверьте запись DNS")
    db.commit()
    return domain


def set_primary(tenant: Tenant, domain: Domain) -> None:
    for d in db.query(Domain).filter_by(tenant_id=tenant.id).all():
        d.is_primary = d.id == domain.id
    tenant.custom_domain = domain.host if domain.verified else tenant.custom_domain
    db.commit()
