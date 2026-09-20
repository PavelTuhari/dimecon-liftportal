"""Прайс компании из командной строки: коэффициенты, зоны, ставки техники.

    python tools/pricing_tool.py show            [--tenant dimecon]
    python tools/pricing_tool.py export  price.json
    python tools/pricing_tool.py import  price.json
    python tools/pricing_tool.py rates-export rates.csv
    python tools/pricing_tool.py rates-import rates.csv   [--apply]

Файл ставок — CSV с колонками: инвентарный номер;машина;ставка за час;мин. смена;подача;помесячно.
"""
from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from portal import create_app  # noqa: E402
from portal.db import SessionLocal as db  # noqa: E402
from portal.models import Equipment, Tenant  # noqa: E402
from portal.services.pricing import DEFAULT_PRICING, pricing_of, pricing_problems  # noqa: E402

HEAD = ["инвентарный", "машина", "ставка за час", "мин. смена, ч", "подача", "помесячно"]


def arg(name: str, default=None):
    if name in sys.argv:
        i = sys.argv.index(name)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


def num(value, default=0.0):
    try:
        return float(str(value).replace(",", ".").strip() or default)
    except ValueError:
        return default


command = sys.argv[1] if len(sys.argv) > 1 else "show"
target = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else None
slug = arg("--tenant", "dimecon")
apply_now = "--apply" in sys.argv

app = create_app()
with app.app_context():
    tenant = db.query(Tenant).filter_by(slug=slug).first()
    if not tenant:
        raise SystemExit(f"компания «{slug}» не найдена")
    fleet = db.query(Equipment).filter_by(tenant_id=tenant.id).order_by(Equipment.capacity_t.desc()).all()

    if command == "show":
        p = pricing_of(tenant)
        print(f"Прайс компании {tenant.name} ({'свой' if tenant.pricing else 'платформенный по умолчанию'})")
        print("\nЗоны подачи:")
        for z in p["zones"]:
            print(f"  {z['name']:<24} плата {z['fee']:>7.0f}  бесплатно {z['free_km']:>3.0f} км  "
                  f"за км {z['per_km']:>5.0f}  до {z['max_km']:>4.0f} км")
        print("\nКоэффициенты времени: " + ", ".join(f"{k}={v}" for k, v in p["time"].items()))
        print("Надбавки за условия:  " + ", ".join(f"{k}={v}" for k, v in p["conditions"].items())
              + f" (потолок {p['conditions_cap']})")
        print("Допуслуги:            " + ", ".join(f"{k}={v:g}" for k, v in p["addons"].items()))
        print("Скидки:               " + ", ".join(f"{k}={v}" for k, v in p["discounts"].items()))
        print("\nСтавки техники:")
        for e in fleet:
            month = (e.spec or {}).get("monthly_rate", 0)
            print(f"  {e.brand} {e.model:<22} час {e.hourly_rate or 0:>7.0f}  мин. смена {e.min_hours or 0:>4.1f}  "
                  f"подача {e.mobilization_fee or 0:>7.0f}" + (f"  помесячно {month:>8.0f}" if month else ""))
        problems = pricing_problems(tenant)
        print("\nЗамечания: " + ("; ".join(problems) if problems else "нет"))

    elif command == "export":
        path = Path(target or "pricing.json")
        path.write_text(json.dumps(pricing_of(tenant), ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Прайс сохранён: {path} ({path.stat().st_size} Б)")

    elif command == "import":
        path = Path(target or "pricing.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        unknown = set(data) - set(DEFAULT_PRICING)
        if unknown:
            print("Внимание, незнакомые разделы будут сохранены как есть: " + ", ".join(sorted(unknown)))
        tenant.pricing = data
        db.commit()
        print(f"Прайс компании {tenant.name} обновлён из {path}")

    elif command == "rates-export":
        path = Path(target or "rates.csv")
        buf = io.StringIO()
        writer = csv.writer(buf, delimiter=";")
        writer.writerow(HEAD)
        for e in fleet:
            writer.writerow([e.inventory_no, f"{e.brand} {e.model}", e.hourly_rate or 0, e.min_hours or 0,
                             e.mobilization_fee or 0, (e.spec or {}).get("monthly_rate", 0)])
        path.write_text("﻿" + buf.getvalue(), encoding="utf-8")
        print(f"Ставки выгружены: {path} ({len(fleet)} машин)")

    elif command == "rates-import":
        path = Path(target or "rates.csv")
        text = path.read_text(encoding="utf-8-sig")
        rows = list(csv.reader(io.StringIO(text), delimiter=";"))[1:]
        by_inv = {(e.inventory_no or "").strip().lower(): e for e in fleet if e.inventory_no}
        by_name = {f"{e.brand} {e.model}".strip().lower(): e for e in fleet}
        changed, missing = 0, []
        for row in rows:
            if len(row) < 3:
                continue
            key_inv, key_name = row[0].strip().lower(), row[1].strip().lower()
            eq = by_inv.get(key_inv) or by_name.get(key_name)
            if eq is None:
                missing.append(row[1] or row[0])
                continue
            new = (num(row[2]), num(row[3]), num(row[4] if len(row) > 4 else 0))
            if new != (eq.hourly_rate, eq.min_hours, eq.mobilization_fee):
                changed += 1
            if apply_now:
                eq.hourly_rate, eq.min_hours, eq.mobilization_fee = new
                month = num(row[5]) if len(row) > 5 else 0
                if month:
                    spec = dict(eq.spec or {})
                    spec["monthly_rate"] = month
                    eq.spec = spec
        if apply_now:
            db.commit()
        print(f"Строк в файле: {len(rows)}; изменится машин: {changed}"
              + (f"; не найдено: {', '.join(missing[:5])}" if missing else ""))
        if not apply_now:
            print("Это предварительный просмотр. Добавьте --apply, чтобы записать ставки.")

    else:
        raise SystemExit(__doc__)
