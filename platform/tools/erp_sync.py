"""Обмен с ERP заказчика по доступам, сохранённым в кабинете.

    python tools/erp_sync.py check                      — проверить оба подключения
    python tools/erp_sync.py officeplus [--apply] [--pages 5]
    python tools/erp_sync.py oracle     [--apply] [--limit 500]
                                        [--tenant dimecon]

Без --apply ничего не записывается: скрипт показывает, что пришло бы в базу.
Доступы берутся из настроек компании (кабинет → Интеграция CRM), в коде их нет.
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from portal import create_app  # noqa: E402
from portal.db import SessionLocal as db  # noqa: E402
from portal.models import Tenant  # noqa: E402
from portal.services import officeplus as op  # noqa: E402
from portal.services import oracle_source as osrc  # noqa: E402


def arg(name: str, default=None):
    if name in sys.argv:
        i = sys.argv.index(name)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


command = sys.argv[1] if len(sys.argv) > 1 else "check"
slug = arg("--tenant", "dimecon")
apply_now = "--apply" in sys.argv

app = create_app()
with app.app_context():
    tenant = db.query(Tenant).filter_by(slug=slug).first()
    if not tenant:
        raise SystemExit(f"компания «{slug}» не найдена")
    settings = tenant.settings or {}
    op_cfg, ora_cfg = settings.get("officeplus") or {}, settings.get("oracle") or {}
    failed = 0

    if command in ("check", "officeplus"):
        if not op_cfg.get("base"):
            print("OfficePlus: доступ не настроен (кабинет → Интеграция CRM)")
            failed += 1
        else:
            client = op.client_from_tenant(tenant)
            try:
                health = client.health()
                print(f"OfficePlus: соединение есть, ответ {health}")
                if command == "officeplus":
                    rep = op.sync_catalog(tenant, client, dry_run=not apply_now,
                                          limit_pages=int(arg("--pages", 5)))
                    print(f"  каталог: {rep.line() if hasattr(rep, 'line') else rep}")
                    if apply_now:
                        op.save_token(tenant, client)
                        db.commit()
            except Exception as exc:  # noqa: BLE001 — показываем причину, не роняем скрипт
                print(f"OfficePlus: не отвечает — {exc}")
                failed += 1

    if command in ("check", "oracle"):
        if not (ora_cfg.get("dsn") and ora_cfg.get("user")):
            print("Oracle: доступ не настроен (кабинет → Интеграция CRM)")
            failed += 1
        else:
            cfg = osrc.OracleConfig(**{k: v for k, v in ora_cfg.items()
                                       if k in osrc.OracleConfig.__dataclass_fields__})
            ok, message = osrc.test_connection(cfg)
            print(f"Oracle: {'соединение есть' if ok else 'не отвечает'} — {message}")
            failed += 0 if ok else 1
            if ok and command == "oracle":
                rep = osrc.import_counterparties(tenant, cfg, dry_run=not apply_now,
                                                 limit=int(arg("--limit", 500)))
                print(f"  контрагенты: {rep.line() if hasattr(rep, 'line') else rep}")
                if apply_now:
                    db.commit()

    if not apply_now and command in ("officeplus", "oracle"):
        print("\nЭто просмотр без записи. Добавьте --apply, чтобы сохранить данные.")

sys.exit(1 if failed else 0)
