"""Наполнение управленческих модулей демо-данными для существующей базы.

    ../.venv/Scripts/python tools/seed_erp.py [slug]
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from portal import create_app  # noqa: E402
from portal.db import SessionLocal as db  # noqa: E402
from portal.models import Tenant  # noqa: E402
from portal.seed_erp import seed_erp  # noqa: E402

slug = sys.argv[1] if len(sys.argv) > 1 else "dimecon"
app = create_app()
with app.app_context():
    tenant = db.query(Tenant).filter_by(slug=slug).first()
    if not tenant:
        raise SystemExit(f"компания «{slug}» не найдена")
    stats = seed_erp(tenant)
    if stats.get("skipped"):
        print(f"{slug}: демо-данные модулей уже есть, ничего не меняю")
    else:
        for key, value in stats.items():
            print(f"  {key:<12} {value}")
        print("ГОТОВО")
