"""Проверка собственных доменов компании: DNS и ответ сайта.

    python tools/domain_check.py                     [--tenant dimecon] [--host eminescu.md]
    python tools/domain_check.py --add crane.dimecon.md

--host — по какому имени отвечает сама платформа (для подсказок DNS).
Код возврата 0, если все домены компании подтверждены.
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from portal import create_app  # noqa: E402
from portal.db import SessionLocal as db  # noqa: E402
from portal.models import Domain, Tenant  # noqa: E402
from portal.services import domains as dom  # noqa: E402


def arg(name: str, default=None):
    if name in sys.argv:
        i = sys.argv.index(name)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


slug = arg("--tenant", "dimecon")
add_host = arg("--add")

app = create_app()
platform_host = arg("--host") or app.config.get("PLATFORM_HOST", "localhost")
with app.app_context():
    tenant = db.query(Tenant).filter_by(slug=slug).first()
    if not tenant:
        raise SystemExit(f"компания «{slug}» не найдена")

    if add_host:
        host = dom.normalize(add_host)
        problem = dom.validate(host)
        if problem:
            raise SystemExit(problem)
        if db.query(Domain).filter_by(host=host).first():
            print(f"{host} уже добавлен")
        else:
            d = Domain(tenant_id=tenant.id, host=host,
                       is_primary=not db.query(Domain).filter_by(tenant_id=tenant.id).count())
            db.add(d)
            db.commit()
            print(f"{host} добавлен")

    rows = db.query(Domain).filter_by(tenant_id=tenant.id).all()
    if not rows:
        print(f"У компании {tenant.name} нет своих доменов — сайт открывается по адресу платформы.")
        print("\nЧто прописать в DNS, когда домен появится:")
        for r in dom.instructions(tenant, f"{tenant.slug}.md", platform_host):
            print(f"  {r['type']:<6} {r['name']:<6} → {r['value']}   ({r['note']})")
        sys.exit(1)

    bad = 0
    for d in rows:
        dom.check(tenant, d, platform_host)
        mark = "OK " if d.verified else "НЕТ"
        bad += 0 if d.verified else 1
        print(f"  {mark} {d.host:<28} DNS: {d.dns_target or '—':<32} HTTP: {d.http_status or '—'}")
        print(f"      {d.check_note}")
        if not d.verified:
            for r in dom.instructions(tenant, d.host, platform_host):
                print(f"      нужна запись {r['type']:<6} {r['name']:<6} → {r['value']}")
    print(f"\nПодтверждено доменов: {len(rows) - bad} из {len(rows)}")
sys.exit(1 if bad else 0)
