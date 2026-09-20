"""Отчёт готовности компании: те же пять пунктов, что в кабинете.

    ../.venv/Scripts/python tools/settings_report.py [slug]

Код возврата 0 — всё настроено, 1 — что-то осталось. Удобно в регулярной проверке.
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from portal import create_app  # noqa: E402
from portal.db import SessionLocal as db  # noqa: E402
from portal.models import Tenant  # noqa: E402
from portal.services import setup_state  # noqa: E402

MARK = {"ok": "[готово]   ", "partial": "[частично] ", "todo": "[осталось] "}

slug = sys.argv[1] if len(sys.argv) > 1 else None
app = create_app()
with app.app_context():
    tenants = ([db.query(Tenant).filter_by(slug=slug).first()] if slug
               else db.query(Tenant).order_by(Tenant.id).all())
    if slug and not tenants[0]:
        raise SystemExit(f"компания «{slug}» не найдена")
    left = 0
    for tenant in tenants:
        state = setup_state.progress(tenant)
        print(f"\n=== {tenant.name} ({tenant.slug}) — готовность {state['pct']} % ===")
        for row in state["rows"]:
            print(f"  {MARK[row['state']]} {row['title']}")
            print(f"              {row['note']}")
            if row["state"] != "ok":
                left += 1
    print(f"\nПунктов осталось: {left}")
sys.exit(1 if left else 0)
