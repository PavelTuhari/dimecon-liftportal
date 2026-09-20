"""Готовность компании к работе: что настроено, что осталось.

Отвечает на вопрос «что дальше» прямо в кабинете: пять пунктов запуска, по каждому —
состояние, короткое объяснение и ссылка на страницу настройки. Тот же расчёт используют
скрипт tools/settings_report.py и проверки.
"""
from __future__ import annotations

from sqlalchemy import func

from ..db import SessionLocal as db
from ..models import Domain, Equipment, Tenant
from . import loadcharts
from .pricing import DEFAULT_PRICING, pricing_of

LEVELS = {"ok": "готово", "partial": "частично", "todo": "не настроено"}


def _charts(tenant: Tenant) -> dict:
    s = loadcharts.summary(tenant)
    if not s["machines"]:
        state, note = "todo", "в парке нет техники"
    elif s["with_passport"] == s["machines"]:
        state, note = "ok", f"паспортные таблицы у всех {s['machines']} машин"
    elif s["with_passport"]:
        state = "partial"
        note = (f"паспорт есть у {s['with_passport']} из {s['machines']}; "
                f"по остальным подбор идёт по ориентировочной кривой")
    else:
        state = "todo"
        note = f"все {s['machines']} машин считаются по ориентировочной кривой с запасом 15 %"
    return {"key": "load_charts", "title": "Грузовые таблицы производителя", "state": state, "note": note,
            "why": "Точный подбор по паспорту вместо оценки: меньше отказов на объекте и споров о вылете.",
            "endpoint": "setup.load_charts", "metrics": s}


def _pricing(tenant: Tenant) -> dict:
    p = pricing_of(tenant)
    own = tenant.pricing or {}
    fleet = db.query(Equipment).filter_by(tenant_id=tenant.id).all()
    no_rate = [e for e in fleet if not (e.hourly_rate or (e.spec or {}).get("monthly_rate"))]
    no_min = [e for e in fleet if e.hourly_rate and not e.min_hours]
    zones = p.get("zones") or []
    problems = []
    if no_rate:
        problems.append(f"без ставки: {len(no_rate)} машин")
    if no_min:
        problems.append(f"без минимальной смены: {len(no_min)}")
    if not own:
        problems.append("коэффициенты и зоны — платформенные по умолчанию")
    if not zones:
        problems.append("не заданы зоны подачи")
    state = "ok" if not problems else ("partial" if own or not no_rate else "todo")
    return {"key": "pricing", "title": "Действующий прайс: ставки, смены, зоны",
            "state": state, "note": "; ".join(problems) or f"ставки у всех {len(fleet)} машин, зон подачи: {len(zones)}",
            "why": "Цена на сайте и в счёте считается по вашему прайсу, а не по демонстрационному.",
            "endpoint": "setup.pricing",
            "metrics": {"fleet": len(fleet), "no_rate": len(no_rate), "no_min": len(no_min),
                        "zones": len(zones), "custom": bool(own)}}


def _company(tenant: Tenant) -> dict:
    need = {"legal_name": "юридическое название", "idno": "IDNO", "bank_name": "банк",
            "bank_iban": "IBAN", "legal_address": "юридический адрес", "director_name": "руководитель"}
    missing = [title for field, title in need.items() if not (getattr(tenant, field, "") or "").strip()]
    smtp = tenant.smtp or {}
    smtp_ok = bool(smtp.get("host") and smtp.get("from_email"))
    if not missing and smtp_ok:
        state, note = "ok", "реквизиты заполнены, почта компании настроена"
    elif missing and not smtp_ok:
        state, note = "todo", "нет реквизитов (" + ", ".join(missing) + ") и почтового сервера"
    else:
        state = "partial"
        note = ("нет: " + ", ".join(missing)) if missing else "реквизиты есть, почтовый сервер не настроен"
    return {"key": "company", "title": "Реквизиты банка и почта для клиентов", "state": state, "note": note,
            "why": "Счета и акты печатаются с вашими реквизитами, письма уходят с вашего адреса.",
            "endpoint": "setup.company", "metrics": {"missing": missing, "smtp": smtp_ok}}


def _integrations(tenant: Tenant) -> dict:
    s = tenant.settings or {}
    op, ora = s.get("officeplus") or {}, s.get("oracle") or {}
    op_ok = bool(op.get("base") and (op.get("token") or (op.get("login") and op.get("password"))))
    ora_ok = bool(ora.get("dsn") and ora.get("user") and ora.get("password"))
    state = "ok" if op_ok and ora_ok else ("partial" if op_ok or ora_ok else "todo")
    parts = []
    parts.append("OfficePlus подключён" if op_ok else "нет доступа к OfficePlus")
    parts.append("Oracle подключён" if ora_ok else "нет доступа к Oracle")
    return {"key": "integrations", "title": "Доступы OfficePlus и Oracle", "state": state,
            "note": ", ".join(parts),
            "why": "Каталог, остатки и контрагенты берутся из вашей ERP, а не заводятся руками.",
            "endpoint": "admin.integrations",
            "metrics": {"officeplus": op_ok, "oracle": ora_ok,
                        "last_sync": s.get("officeplus", {}).get("last_sync"),
                        "last_oracle": s.get("oracle", {}).get("last_import")}}


def _domain(tenant: Tenant) -> dict:
    rows = db.query(Domain).filter_by(tenant_id=tenant.id).all()
    verified = [d for d in rows if d.verified]
    if verified:
        state, note = "ok", "работает: " + ", ".join(d.host for d in verified)
    elif rows:
        state, note = "partial", "домен добавлен, но проверка не прошла: " + ", ".join(d.host for d in rows)
    else:
        state, note = "todo", "сайт открывается по адресу платформы"
    return {"key": "domain", "title": "Свой домен вместо адреса платформы", "state": state, "note": note,
            "why": "Клиенты видят ваш адрес, письма и ссылки в документах — тоже.",
            "endpoint": "setup.domain", "metrics": {"domains": len(rows), "verified": len(verified)}}


def checklist(tenant: Tenant) -> list[dict]:
    return [_charts(tenant), _pricing(tenant), _company(tenant), _integrations(tenant), _domain(tenant)]


def progress(tenant: Tenant) -> dict:
    rows = checklist(tenant)
    done = len([r for r in rows if r["state"] == "ok"])
    partial = len([r for r in rows if r["state"] == "partial"])
    return {"rows": rows, "done": done, "partial": partial, "total": len(rows),
            "pct": round((done + partial * 0.5) / len(rows) * 100)}
